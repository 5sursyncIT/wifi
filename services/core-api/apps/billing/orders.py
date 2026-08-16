"""Order creation and state transitions (cahier des charges §8.5, §10.4).

Every transition lives here. No status is written anywhere else, so the set of legal
moves can be read in one place rather than reconstructed from call sites.

Known window, left open on purpose: two concurrent retries of the same still-DRAFT
order can each reach the provider call in `place_order` and each start a payment
intent for that one order. Closing it by reserving the order — moving it to PENDING
before the provider call — would trade that window for a worse one: a status that
claims payment started whenever the call fails or times out. Passing the order's own
idempotency key through to `provider.create_payment` may let the provider de-duplicate
the second attempt; the contract already hands the whole order to `create_payment`, but
whether that works needs confirming per provider in sandbox (ADR-0004 commits phase 7
to verifying push capability there, not idempotency-key de-duplication explicitly).
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.billing.models import Order, Payment
from apps.billing.providers import get_payment_provider
from apps.billing.providers.base import PaymentError
from apps.catalog.models import Plan

logger = logging.getLogger(__name__)


class OrderRefused(Exception):
    """The order cannot be placed. `reason` is a stable machine-readable code."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


class InvalidTransition(Exception):
    """The order is not in a state where this move is allowed."""


# What each status may become. Absent keys are terminal.
_ALLOWED: dict[str, set[str]] = {
    Order.Status.DRAFT: {
        Order.Status.PENDING,
        Order.Status.REQUIRES_ACTION,
        Order.Status.CANCELLED,
    },
    Order.Status.PENDING: {
        Order.Status.REQUIRES_ACTION,
        Order.Status.PAID,
        Order.Status.FAILED,
        Order.Status.EXPIRED,
        Order.Status.CANCELLED,
    },
    Order.Status.REQUIRES_ACTION: {
        Order.Status.PAID,
        Order.Status.FAILED,
        Order.Status.EXPIRED,
        Order.Status.CANCELLED,
    },
    # An expired order may still be paid: the confirmation simply arrived late (§8.5).
    Order.Status.EXPIRED: {Order.Status.PAID},
}


def _move(order: Order, target: str, fields: list[str]) -> Order:
    if target not in _ALLOWED.get(order.status, set()):
        raise InvalidTransition(
            f"Order {order.order_number} cannot move from {order.status} to {target}."
        )
    order.status = target
    order.save(update_fields=[*fields, "status", "updated_at"])
    return order


def place_order(citizen, zone, plan_version, idempotency_key: str) -> tuple[Order, Payment | None]:
    """Create the order, then ask the provider to start a payment.

    The order is committed before the provider is called: a webhook can legitimately
    arrive before the browser comes back (§16.1), and it must find an order to match.

    An existing non-DRAFT order under the same idempotency key is returned immediately
    without re-validating the catalogue (§10.4). Catalogue checks run only when
    creating a new order or resuming a still-DRAFT one.

    `get_or_create` — rather than a hand-rolled filter-then-create — is what keeps two
    simultaneous first attempts for the same key from both racing into the
    `one_order_per_idempotency_key` constraint: Django retries the read itself when
    the create loses that race, so the loser gets the winner's row back instead of an
    unhandled `IntegrityError`.

    The returned payment is `None` only when the replayed key points at an order that
    was cancelled while still a draft (the sole non-draft state `_ALLOWED` lets a draft
    reach without a `Payment` ever being created — creation is atomic with the
    PENDING/REQUIRES_ACTION move below). That is a legitimate terminal state, not a
    data inconsistency, so callers must be able to observe it rather than have it
    papered over by a type that promises a payment that does not exist.
    """
    existing = Order.objects.filter(citizen=citizen, idempotency_key=idempotency_key).first()
    if existing is not None and existing.status != Order.Status.DRAFT:
        # Replaying the key must not charge twice (§10.4).
        payment = existing.payments.order_by("-created_at").first()
        return existing, payment

    if not citizen.is_usable:
        raise OrderRefused("account_unusable", "Ce compte ne peut pas être utilisé.")

    plan = plan_version.plan
    if plan.status != Plan.Status.PUBLISHED or plan.current_version_id != plan_version.pk:
        raise OrderRefused("offer_unavailable", "Cette offre n'est plus disponible.")

    if not plan.zones.filter(pk=zone.pk).exists():
        raise OrderRefused("offer_unavailable", "Cette offre n'est pas proposée ici.")

    if existing is not None:
        order = existing
    else:
        order, _created = Order.objects.get_or_create(
            citizen=citizen,
            idempotency_key=idempotency_key,
            defaults={
                "plan_version": plan_version,
                "zone": zone,
                # Frozen here and never read from the plan again: a later price change
                # must not be retroactive (§8.3).
                "amount_xof": plan_version.price_xof,
                "currency": settings.DEFAULT_CURRENCY,
                "expires_at": timezone.now()
                + timedelta(seconds=settings.ORDER_PENDING_TTL_SECONDS),
            },
        )
        if order.status != Order.Status.DRAFT:
            payment = order.payments.order_by("-created_at").first()
            return order, payment

    provider = get_payment_provider()
    try:
        intent = provider.create_payment(order)
    except PaymentError as error:
        logger.warning("Payment initiation failed for %s: %s", order.order_number, error)
        raise OrderRefused(
            "provider_unavailable", "Le paiement est momentanément indisponible."
        ) from error

    with transaction.atomic():
        payment = Payment.objects.create(
            order=order,
            provider=provider.name,
            mode=intent.mode,
            external_reference=intent.external_reference,
            amount_xof=order.amount_xof,
        )
        target = (
            Order.Status.REQUIRES_ACTION
            if intent.mode == Payment.Mode.REDIRECT
            else Order.Status.PENDING
        )
        _move(order, target, [])

    return order, payment


def mark_paid(order: Order, *, fees_xof: int = 0) -> Order:
    was_expired = order.status == Order.Status.EXPIRED
    order.paid_at = timezone.now()
    if was_expired:
        order.reactivated_after_expiry = True
        logger.warning(
            "Order %s confirmed after expiry: reactivated for reconciliation (§8.5).",
            order.order_number,
        )
    _move(order, Order.Status.PAID, ["paid_at", "reactivated_after_expiry"])
    order.payments.filter(status=Payment.Status.INITIATED).update(
        status=Payment.Status.SUCCEEDED, fees_xof=fees_xof
    )
    return order


def mark_failed(order: Order) -> Order:
    _move(order, Order.Status.FAILED, [])
    order.payments.filter(status=Payment.Status.INITIATED).update(status=Payment.Status.REFUSED)
    return order


def expire(order: Order) -> Order:
    order.expired_at = timezone.now()
    _move(order, Order.Status.EXPIRED, ["expired_at"])
    order.payments.filter(status=Payment.Status.INITIATED).update(status=Payment.Status.EXPIRED)
    return order


def cancel(order: Order) -> Order:
    order.cancelled_at = timezone.now()
    return _move(order, Order.Status.CANCELLED, ["cancelled_at"])
