"""Scheduled work behind the purchase chain (§8.5)."""

import pytest
from django.utils import timezone

from apps.billing.models import Order
from apps.billing.orders import place_order
from apps.billing.providers.mock import MockPaymentProvider
from apps.billing.tasks import expire_pending_orders, reconcile_pending_payments


@pytest.fixture(autouse=True)
def reset_provider():
    MockPaymentProvider.reset()
    yield
    MockPaymentProvider.reset()


@pytest.fixture
def placed(citizen, zone, plan_version):
    order, _ = place_order(citizen, zone, plan_version, "key-1")
    return order


def test_an_order_past_its_deadline_expires(placed):
    Order.objects.update(expires_at=timezone.now() - timezone.timedelta(minutes=1))

    assert expire_pending_orders() == 1

    placed.refresh_from_db()
    assert placed.status == Order.Status.EXPIRED


def test_an_order_still_within_its_deadline_is_left_alone(placed):
    assert expire_pending_orders() == 0

    placed.refresh_from_db()
    assert placed.status == Order.Status.PENDING


def test_a_paid_order_is_never_expired(placed):
    Order.objects.update(
        status=Order.Status.PAID, expires_at=timezone.now() - timezone.timedelta(minutes=1)
    )

    assert expire_pending_orders() == 0


def test_reconciliation_pays_an_order_the_provider_reports_as_settled(placed, settings):
    settings.PAYMENT_RECONCILE_AFTER_SECONDS = 0
    MockPaymentProvider.statuses[MockPaymentProvider.reference_for(placed)] = "succeeded"

    assert reconcile_pending_payments() == 1

    placed.refresh_from_db()
    assert placed.status == Order.Status.PAID


def test_reconciliation_leaves_a_still_pending_payment_alone(placed, settings):
    settings.PAYMENT_RECONCILE_AFTER_SECONDS = 0

    assert reconcile_pending_payments() == 0

    placed.refresh_from_db()
    assert placed.status == Order.Status.PENDING
