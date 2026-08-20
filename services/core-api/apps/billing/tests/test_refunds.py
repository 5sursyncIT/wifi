"""Refunds, order transitions and provider mock (§8.5, DW-P6-03)."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.billing.models import Order, Payment, Refund
from apps.billing.providers.mock import MockPaymentProvider
from apps.billing.refunds import RefundRefused, refund_payment


@pytest.fixture(autouse=True)
def reset_provider():
    MockPaymentProvider.reset()
    yield
    MockPaymentProvider.reset()


@pytest.fixture
def succeeded_payment(order):
    order.status = Order.Status.PAID
    order.paid_at = timezone.now()
    order.save(update_fields=["status", "paid_at"])
    return Payment.objects.create(
        order=order,
        provider="mock",
        mode=Payment.Mode.PUSH,
        external_reference=f"MOCK-{order.order_number}",
        amount_xof=order.amount_xof,
        status=Payment.Status.SUCCEEDED,
    )


@pytest.fixture
def financier(db):
    return get_user_model().objects.create_user("demo_financier", password="x", is_staff=True)


def test_a_full_refund_marks_the_order_refunded(succeeded_payment, financier):
    refund = refund_payment(succeeded_payment, succeeded_payment.amount_xof, "erreur", financier)

    assert refund.status == Refund.Status.SUCCEEDED
    succeeded_payment.order.refresh_from_db()
    assert succeeded_payment.order.status == Order.Status.REFUNDED


def test_a_partial_refund_marks_the_order_partially_refunded(succeeded_payment, financier):
    refund_payment(succeeded_payment, 100, "partiel", financier)

    succeeded_payment.order.refresh_from_db()
    assert succeeded_payment.order.status == Order.Status.PARTIALLY_REFUNDED


def test_refunding_more_than_the_payment_is_refused(succeeded_payment, financier):
    with pytest.raises(RefundRefused) as raised:
        refund_payment(succeeded_payment, succeeded_payment.amount_xof + 1, "trop", financier)

    assert raised.value.reason == "amount_exceeds_payment"
    assert Refund.objects.count() == 0


def test_two_partial_refunds_can_complete_the_payment(succeeded_payment, financier):
    refund_payment(succeeded_payment, 200, "a", financier)
    refund_payment(succeeded_payment, succeeded_payment.amount_xof - 200, "b", financier)

    succeeded_payment.order.refresh_from_db()
    assert succeeded_payment.order.status == Order.Status.REFUNDED
    assert Refund.objects.filter(status=Refund.Status.SUCCEEDED).count() == 2


def test_a_non_succeeded_payment_cannot_be_refunded(order, financier):
    payment = Payment.objects.create(
        order=order,
        provider="mock",
        mode=Payment.Mode.PUSH,
        external_reference="MOCK-X",
        amount_xof=order.amount_xof,
        status=Payment.Status.INITIATED,
    )

    with pytest.raises(RefundRefused) as raised:
        refund_payment(payment, 100, "non", financier)

    assert raised.value.reason == "payment_not_succeeded"
