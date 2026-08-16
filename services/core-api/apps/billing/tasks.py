"""Scheduled work owned by billing (cahier des charges §8.5)."""

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.access.activation import TOPIC, entitlement_for_order
from apps.billing.models import Order
from apps.billing.orders import InvalidTransition, expire, mark_paid
from apps.billing.providers import get_payment_provider
from apps.core.outbox import enqueue

logger = logging.getLogger(__name__)


@shared_task(name="billing.expire_pending_orders")
def expire_pending_orders() -> int:
    """Close orders nobody paid within the configured window."""
    due = Order.objects.filter(
        status__in=[Order.Status.PENDING, Order.Status.REQUIRES_ACTION],
        expires_at__lte=timezone.now(),
    )
    count = 0
    for order in due:
        try:
            expire(order)
        except InvalidTransition:
            continue
        count += 1
    return count


@shared_task(name="billing.reconcile_pending_payments")
def reconcile_pending_payments() -> int:
    """Ask the provider about orders that stayed pending (§8.5).

    A webhook can be lost. Polling is the safety net that keeps a paid citizen from
    waiting on a message that never arrives.
    """
    threshold = timezone.now() - timedelta(seconds=settings.PAYMENT_RECONCILE_AFTER_SECONDS)
    stale = Order.objects.filter(
        status__in=[Order.Status.PENDING, Order.Status.REQUIRES_ACTION],
        created_at__lte=threshold,
    ).prefetch_related("payments")

    provider = get_payment_provider()
    settled = 0
    for order in stale:
        payment = order.payments.order_by("-created_at").first()
        if payment is None:
            continue
        status = provider.get_payment_status(payment.external_reference)
        if status.status != "succeeded":
            continue
        # Same rule as the webhook path: state and outbox row commit together, and the
        # network call happens afterwards. Reconciliation must not be the one place
        # where a payment can be recorded without its activation being scheduled.
        with transaction.atomic():
            mark_paid(order, fees_xof=status.fees_xof)
            entitlement = entitlement_for_order(order, starts_at=timezone.now())
            enqueue(TOPIC, {"entitlement_id": str(entitlement.pk)})
        logger.warning("Order %s settled by reconciliation, not by webhook.", order.order_number)
        settled += 1
    return settled
