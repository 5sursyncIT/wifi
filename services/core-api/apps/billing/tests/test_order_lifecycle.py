"""Order creation, idempotency and state transitions (§8.5, §10.4)."""

import pytest
from django.utils import timezone

from apps.billing.models import Order, Payment
from apps.billing.orders import (
    InvalidTransition,
    OrderRefused,
    cancel,
    expire,
    mark_failed,
    mark_paid,
    place_order,
)
from apps.billing.providers.mock import MockPaymentProvider
from apps.catalog.models import Plan, PlanVersion


@pytest.fixture(autouse=True)
def reset_provider():
    MockPaymentProvider.reset()
    yield
    MockPaymentProvider.reset()


def test_placing_an_order_initiates_a_push_payment(citizen, zone, plan_version):
    order, payment = place_order(citizen, zone, plan_version, "key-1")

    assert order.status == Order.Status.PENDING
    assert order.amount_xof == plan_version.price_xof
    assert order.expires_at > timezone.now()
    assert payment.mode == Payment.Mode.PUSH
    assert payment.status == Payment.Status.INITIATED


def test_the_redirect_fallback_puts_the_order_in_requires_action(citizen, zone, plan_version):
    MockPaymentProvider.scenario = "redirect_required"

    order, payment = place_order(citizen, zone, plan_version, "key-1")

    assert order.status == Order.Status.REQUIRES_ACTION
    assert payment.mode == Payment.Mode.REDIRECT


def test_replaying_an_idempotency_key_returns_the_same_order(citizen, zone, plan_version):
    first, _ = place_order(citizen, zone, plan_version, "key-1")
    second, _ = place_order(citizen, zone, plan_version, "key-1")

    assert first.pk == second.pk
    assert Order.objects.count() == 1


def test_an_unpublished_plan_cannot_be_bought(citizen, zone, plan, plan_version):
    plan.status = Plan.Status.DRAFT
    plan.save(update_fields=["status"])

    with pytest.raises(OrderRefused) as raised:
        place_order(citizen, zone, plan_version, "key-1")

    assert raised.value.reason == "offer_unavailable"


def test_a_provider_outage_leaves_no_half_created_order(citizen, zone, plan_version):
    MockPaymentProvider.scenario = "provider_unavailable"

    with pytest.raises(OrderRefused) as raised:
        place_order(citizen, zone, plan_version, "key-1")

    assert raised.value.reason == "provider_unavailable"
    # The draft is kept so the same idempotency key can be retried without colliding,
    # but it is never left as if payment had started.
    assert Order.objects.get().status == Order.Status.DRAFT


def test_a_draft_can_be_resumed_after_a_provider_outage(citizen, zone, plan_version):
    MockPaymentProvider.scenario = "provider_unavailable"
    with pytest.raises(OrderRefused):
        place_order(citizen, zone, plan_version, "key-1")

    MockPaymentProvider.scenario = "push_success"
    order, _ = place_order(citizen, zone, plan_version, "key-1")

    assert Order.objects.count() == 1
    assert Payment.objects.count() == 1
    assert order.status == Order.Status.PENDING


def test_a_later_price_change_does_not_alter_a_placed_order(citizen, zone, plan, plan_version):
    first, _ = place_order(citizen, zone, plan_version, "key-1")

    new_version = PlanVersion.objects.create(
        plan=plan,
        version=2,
        price_xof=99_000,
        connection_seconds=3600,
        radius_profile_ref="dakar-1h",
        effective_at=timezone.now(),
    )
    plan.current_version = new_version
    plan.save(update_fields=["current_version"])

    second, _ = place_order(citizen, zone, new_version, "key-2")

    first.refresh_from_db()
    assert first.amount_xof == plan_version.price_xof
    assert second.amount_xof == new_version.price_xof


def test_paying_an_order_stamps_it(citizen, zone, plan_version):
    order, _ = place_order(citizen, zone, plan_version, "key-1")

    mark_paid(order)

    order.refresh_from_db()
    assert order.status == Order.Status.PAID
    assert order.paid_at is not None


def test_an_expired_order_can_still_be_paid_and_is_flagged(citizen, zone, plan_version):
    # §8.5: the citizen paid, so the right is granted; the discrepancy goes to
    # reconciliation rather than being refused.
    order, _ = place_order(citizen, zone, plan_version, "key-1")
    expire(order)

    mark_paid(order)

    order.refresh_from_db()
    assert order.status == Order.Status.PAID
    assert order.reactivated_after_expiry is True


def test_a_cancelled_order_cannot_be_paid(citizen, zone, plan_version):
    order, _ = place_order(citizen, zone, plan_version, "key-1")
    cancel(order)

    with pytest.raises(InvalidTransition):
        mark_paid(order)


def test_a_refused_payment_fails_the_order(citizen, zone, plan_version):
    order, _ = place_order(citizen, zone, plan_version, "key-1")

    mark_failed(order)

    order.refresh_from_db()
    assert order.status == Order.Status.FAILED
