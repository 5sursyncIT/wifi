"""Audited payment CSV export without personal data (§8.13, §13.3)."""

import csv
import io

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.billing.exports import payments_csv
from apps.billing.models import Order, Payment
from apps.core.models import AuditLog


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
        fees_xof=25,
        status=Payment.Status.SUCCEEDED,
    )


def test_the_csv_has_no_phone_number(succeeded_payment):
    actor = get_user_model().objects.create_user("financier", password="x")
    output = payments_csv(Payment.objects.all(), actor=actor)
    text = output.decode("utf-8")

    assert succeeded_payment.order.citizen.phone_e164 not in text
    reader = csv.DictReader(io.StringIO(text))
    row = next(reader)
    assert row["order_number"] == succeeded_payment.order.order_number
    assert row["amount_xof"] == str(succeeded_payment.amount_xof)
    assert row["zone_code"] == succeeded_payment.order.zone.code
    assert "phone" not in row


def test_an_export_is_audited(succeeded_payment):
    actor = get_user_model().objects.create_user("financier", password="x")
    payments_csv(Payment.objects.all(), actor=actor)

    event = AuditLog.objects.get(action="payment.export")
    assert event.actor_id == actor.pk
