"""Financial reconciliation against the payment provider (§8.13)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.billing.models import Order, Payment, ReconciliationRun
from apps.billing.providers.mock import MockPaymentProvider
from apps.billing.reconciliation import run_reconciliation


@pytest.fixture(autouse=True)
def reset_provider():
    MockPaymentProvider.reset()
    yield
    MockPaymentProvider.reset()


def _succeeded_payment(order, amount=None):
    order.status = Order.Status.PAID
    order.paid_at = timezone.now()
    order.save(update_fields=["status", "paid_at"])
    reference = f"MOCK-{order.order_number}"
    amount = order.amount_xof if amount is None else amount
    MockPaymentProvider.statuses[reference] = "succeeded"
    MockPaymentProvider.amounts[reference] = amount
    return Payment.objects.create(
        order=order,
        provider="mock",
        mode=Payment.Mode.PUSH,
        external_reference=reference,
        amount_xof=order.amount_xof,
        status=Payment.Status.SUCCEEDED,
    )


def test_a_matching_period_is_balanced(order):
    _succeeded_payment(order)
    start = timezone.now() - timedelta(hours=1)
    end = timezone.now() + timedelta(hours=1)

    run = run_reconciliation("mock", start, end)

    assert run.status == ReconciliationRun.Status.BALANCED
    assert run.totals_json["mismatch_count"] == 0
    assert run.totals_json["local_succeeded_xof"] == order.amount_xof


def test_an_amount_divergence_is_a_mismatch(order):
    _succeeded_payment(order)
    MockPaymentProvider.amounts[f"MOCK-{order.order_number}"] = order.amount_xof - 50
    start = timezone.now() - timedelta(hours=1)
    end = timezone.now() + timedelta(hours=1)

    run = run_reconciliation("mock", start, end)

    assert run.status == ReconciliationRun.Status.MISMATCH
    assert run.totals_json["mismatch_count"] == 1
