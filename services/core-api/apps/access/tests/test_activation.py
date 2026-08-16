"""Activating a paid right through the outbox (§8.5, §11.2, §17 no 6)."""

import pytest
from django.utils import timezone

from apps.access.activation import TOPIC, activate_entitlement, entitlement_for_order
from apps.access.models import Entitlement
from apps.access.providers.mock import MockNetworkProvider
from apps.billing.models import Order


@pytest.fixture(autouse=True)
def reset_provider():
    MockNetworkProvider.reset()
    yield
    MockNetworkProvider.reset()


@pytest.fixture
def paid_order(order):
    order.status = Order.Status.PAID
    order.paid_at = timezone.now()
    order.save(update_fields=["status", "paid_at"])
    return order


def test_the_topic_is_the_one_the_outbox_registers():
    assert TOPIC == "entitlement.activate"


def test_creating_the_right_leaves_it_waiting_for_the_network(paid_order):
    entitlement = entitlement_for_order(paid_order, starts_at=timezone.now())

    assert entitlement.status == Entitlement.Status.PENDING_ACTIVATION
    assert entitlement.source == Entitlement.Source.PURCHASE
    assert entitlement.order_id == paid_order.pk


def test_creating_the_right_twice_returns_the_same_one(paid_order):
    first = entitlement_for_order(paid_order, starts_at=timezone.now())
    second = entitlement_for_order(paid_order, starts_at=timezone.now())

    assert first.pk == second.pk
    assert Entitlement.objects.count() == 1


def test_activation_applies_the_plan_and_marks_the_right_active(paid_order):
    entitlement = entitlement_for_order(paid_order, starts_at=timezone.now())

    activate_entitlement({"entitlement_id": str(entitlement.pk)})

    entitlement.refresh_from_db()
    assert entitlement.status == Entitlement.Status.ACTIVE
    assert entitlement.radius_username == str(paid_order.citizen_id)
    assert MockNetworkProvider.assignments[str(paid_order.citizen_id)] == (
        paid_order.plan_version.radius_profile_ref
    )


def test_activation_is_idempotent(paid_order):
    # §16.1: replaying an activation must not apply the plan a second time.
    entitlement = entitlement_for_order(paid_order, starts_at=timezone.now())
    activate_entitlement({"entitlement_id": str(entitlement.pk)})
    calls_after_first = MockNetworkProvider.assignment_calls

    activate_entitlement({"entitlement_id": str(entitlement.pk)})

    assert MockNetworkProvider.assignment_calls == calls_after_first


def test_a_network_outage_raises_so_the_outbox_retries(paid_order):
    entitlement = entitlement_for_order(paid_order, starts_at=timezone.now())
    MockNetworkProvider.scenario = "temporary_error"

    with pytest.raises(Exception):  # noqa: B017 - the outbox catches any failure
        activate_entitlement({"entitlement_id": str(entitlement.pk)})

    entitlement.refresh_from_db()
    # Crucially still pending, not failed: the citizen paid, so this must be retried.
    assert entitlement.status == Entitlement.Status.PENDING_ACTIVATION
