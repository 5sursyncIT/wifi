import pytest
from django.test import override_settings
from django.utils import timezone

from apps.access.activation import entitlement_for_order
from apps.access.models import Entitlement
from apps.access.providers.mock import MockNetworkProvider
from apps.access.tasks import reconcile_active_entitlements
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


def test_reconcile_is_a_noop_on_the_mock_provider(paid_order):
    entitlement = entitlement_for_order(paid_order, starts_at=timezone.now())
    entitlement.status = Entitlement.Status.ACTIVE
    entitlement.save(update_fields=["status", "updated_at"])

    assert reconcile_active_entitlements() == 0
    assert MockNetworkProvider.assignment_calls == 0


@override_settings(NETWORK_PROVIDER="openwisp")
def test_reconcile_reassigns_active_entitlements(paid_order, monkeypatch):
    entitlement = entitlement_for_order(paid_order, starts_at=timezone.now())
    entitlement.status = Entitlement.Status.ACTIVE
    entitlement.save(update_fields=["status", "updated_at"])

    calls: list[tuple[str, str]] = []

    class Fake:
        def ensure_user(self, subscriber_ref: str) -> str:
            return subscriber_ref

        def assign_plan(self, subscriber_ref: str, profile_ref: str):
            calls.append((subscriber_ref, profile_ref))

    monkeypatch.setattr("apps.access.tasks.get_network_provider", lambda: Fake())

    assert reconcile_active_entitlements() == 1
    assert calls == [(str(paid_order.citizen_id), paid_order.plan_version.radius_profile_ref)]
