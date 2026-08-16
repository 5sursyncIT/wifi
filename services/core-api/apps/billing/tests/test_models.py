"""What the database itself guarantees about the financial chain (§8.5, §17 no 5)."""

from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.access.models import Entitlement
from apps.billing.models import Order, WebhookEvent


def test_an_order_number_is_assigned_and_unique(order, citizen, zone, plan_version):
    second = Order.objects.create(
        citizen=citizen,
        plan_version=plan_version,
        zone=zone,
        amount_xof=plan_version.price_xof,
        currency="XOF",
        idempotency_key="key-2",
        expires_at=timezone.now() + timedelta(minutes=30),
    )

    assert order.order_number
    assert order.order_number != second.order_number


def test_the_same_idempotency_key_cannot_create_two_orders(order, citizen, zone, plan_version):
    with pytest.raises(IntegrityError), transaction.atomic():
        Order.objects.create(
            citizen=citizen,
            plan_version=plan_version,
            zone=zone,
            amount_xof=plan_version.price_xof,
            currency="XOF",
            idempotency_key=order.idempotency_key,
            expires_at=timezone.now() + timedelta(minutes=30),
        )


def test_only_one_delivery_per_event_may_be_processed(order):
    WebhookEvent.objects.create(
        provider="mock",
        external_event_id="EVT-1",
        order=order,
        signature_valid=True,
        outcome=WebhookEvent.Outcome.PROCESSED,
    )

    # A duplicate delivery may be recorded — the history must be complete (§8.5) —
    # but never as a second processed one.
    WebhookEvent.objects.create(
        provider="mock",
        external_event_id="EVT-1",
        order=order,
        signature_valid=True,
        outcome=WebhookEvent.Outcome.DUPLICATE,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        WebhookEvent.objects.create(
            provider="mock",
            external_event_id="EVT-1",
            order=order,
            signature_valid=True,
            outcome=WebhookEvent.Outcome.PROCESSED,
        )


def test_an_order_can_carry_only_one_entitlement(order, plan_version, citizen, zone):
    Entitlement.objects.create(
        citizen=citizen,
        plan_version=plan_version,
        zone=zone,
        order=order,
        source=Entitlement.Source.PURCHASE,
        starts_at=timezone.now(),
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        Entitlement.objects.create(
            citizen=citizen,
            plan_version=plan_version,
            zone=zone,
            order=order,
            source=Entitlement.Source.PURCHASE,
            starts_at=timezone.now(),
        )
