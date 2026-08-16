"""Webhook reception (cahier des charges §8.5, §10.2, §16.1).

Trust rests entirely on the signature: this endpoint has no authentication, because the
provider has no session. Every delivery is recorded — duplicates and rejections included
— and exactly one may ever be marked processed, which the database enforces.
"""

import hashlib
import logging
from collections.abc import Mapping
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.access.activation import TOPIC, entitlement_for_order
from apps.billing.models import Order, WebhookEvent
from apps.billing.orders import InvalidTransition, mark_failed, mark_paid
from apps.billing.providers import get_payment_provider, is_known_provider
from apps.core.outbox import enqueue

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WebhookResult:
    outcome: str
    http_status: int


def _record(
    provider_name,
    event_id,
    body,
    *,
    outcome,
    order=None,
    signature_valid=False,
    payload=None,
) -> WebhookEvent:
    return WebhookEvent.objects.create(
        provider=provider_name,
        external_event_id=event_id,
        order=order,
        signature_valid=signature_valid,
        outcome=outcome,
        payload=payload or {},
        body_sha256=hashlib.sha256(body).hexdigest(),
        processed_at=(timezone.now() if outcome == WebhookEvent.Outcome.PROCESSED else None),
    )


def handle(provider_name: str, headers: Mapping[str, str], body: bytes) -> WebhookResult:
    if not is_known_provider(provider_name):
        return WebhookResult(WebhookEvent.Outcome.IGNORED, 404)

    provider = get_payment_provider()

    if not provider.verify_webhook(headers, body):
        # 400 and not 500: a signature that is wrong will never become right, so
        # asking the provider to retry would be pointless noise.
        _record(provider_name, "", body, outcome=WebhookEvent.Outcome.BAD_SIGNATURE)
        logger.warning("Rejected a %s webhook with an invalid signature.", provider_name)
        return WebhookResult(WebhookEvent.Outcome.BAD_SIGNATURE, 400)

    event = provider.parse_webhook(body)
    # Only what an investigation needs. The raw body is never kept: it may carry
    # secrets, and §9 forbids a full copy when a reduced one suffices.
    minimised = {
        "event_id": event.external_event_id,
        "reference": event.external_reference,
        "status": event.status,
        "amount": event.amount_xof,
        "currency": event.currency,
    }

    order = Order.objects.filter(payments__external_reference=event.external_reference).first()
    if order is None:
        _record(
            provider_name,
            event.external_event_id,
            body,
            outcome=WebhookEvent.Outcome.UNKNOWN_ORDER,
            signature_valid=True,
            payload=minimised,
        )
        return WebhookResult(WebhookEvent.Outcome.UNKNOWN_ORDER, 404)

    # Strict comparison, never tolerant (§8.5).
    if (
        event.amount_xof != order.amount_xof
        or event.currency != order.currency
        or event.payee != provider.expected_payee
    ):
        _record(
            provider_name,
            event.external_event_id,
            body,
            outcome=WebhookEvent.Outcome.AMOUNT_MISMATCH,
            order=order,
            signature_valid=True,
            payload=minimised,
        )
        logger.error("Webhook for %s diverges from the order.", order.order_number)
        return WebhookResult(WebhookEvent.Outcome.AMOUNT_MISMATCH, 400)

    if event.status != "succeeded":
        try:
            mark_failed(order)
        except InvalidTransition:
            pass
        _record(
            provider_name,
            event.external_event_id,
            body,
            outcome=WebhookEvent.Outcome.PROCESSED,
            order=order,
            signature_valid=True,
            payload=minimised,
        )
        return WebhookResult(WebhookEvent.Outcome.PROCESSED, 200)

    try:
        with transaction.atomic():
            # Everything that must survive commits together; the network call happens
            # afterwards, driven by the outbox row written here.
            _record(
                provider_name,
                event.external_event_id,
                body,
                outcome=WebhookEvent.Outcome.PROCESSED,
                order=order,
                signature_valid=True,
                payload=minimised,
            )
            mark_paid(order, fees_xof=event.fees_xof)
            entitlement = entitlement_for_order(order, starts_at=timezone.now())
            enqueue(TOPIC, {"entitlement_id": str(entitlement.pk)})
    except IntegrityError:
        # The partial unique index refused a second processed delivery: this is a
        # duplicate. Recorded for the history, not replayed.
        _record(
            provider_name,
            event.external_event_id,
            body,
            outcome=WebhookEvent.Outcome.DUPLICATE,
            order=order,
            signature_valid=True,
            payload=minimised,
        )
        return WebhookResult(WebhookEvent.Outcome.DUPLICATE, 200)

    return WebhookResult(WebhookEvent.Outcome.PROCESSED, 200)
