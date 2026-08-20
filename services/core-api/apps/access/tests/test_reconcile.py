from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.access.activation import entitlement_for_order
from apps.access.models import Entitlement
from apps.access.providers.base import NetworkPermanentError
from apps.access.providers.mock import MockNetworkProvider
from apps.access.tasks import reconcile_active_entitlements
from apps.billing.models import Order
from apps.core.models import OutboxMessage


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
    call_order: list[str] = []

    class Fake:
        def ensure_user(self, subscriber_ref: str) -> str:
            call_order.append("ensure_user")
            return subscriber_ref

        def assign_plan(self, subscriber_ref: str, profile_ref: str):
            call_order.append("assign_plan")
            calls.append((subscriber_ref, profile_ref))

    monkeypatch.setattr("apps.access.tasks.get_network_provider", lambda: Fake())

    assert reconcile_active_entitlements() == 1
    assert calls == [(str(paid_order.citizen_id), paid_order.plan_version.radius_profile_ref)]
    assert call_order == ["ensure_user", "assign_plan"]


@override_settings(NETWORK_PROVIDER="openwisp")
def test_reconcile_skips_pending_activation(paid_order, monkeypatch):
    entitlement_for_order(paid_order, starts_at=timezone.now())

    calls: list[tuple[str, str]] = []

    class Fake:
        def ensure_user(self, subscriber_ref: str) -> str:
            return subscriber_ref

        def assign_plan(self, subscriber_ref: str, profile_ref: str):
            calls.append((subscriber_ref, profile_ref))

    monkeypatch.setattr("apps.access.tasks.get_network_provider", lambda: Fake())

    assert reconcile_active_entitlements() == 0
    assert calls == []


@override_settings(NETWORK_PROVIDER="openwisp")
def test_reconcile_skips_expired_active_entitlements(paid_order, monkeypatch):
    entitlement = entitlement_for_order(paid_order, starts_at=timezone.now())
    entitlement.status = Entitlement.Status.ACTIVE
    entitlement.ends_at = timezone.now() - timedelta(minutes=1)
    entitlement.save(update_fields=["status", "ends_at", "updated_at"])

    calls: list[tuple[str, str]] = []

    class Fake:
        def ensure_user(self, subscriber_ref: str) -> str:
            return subscriber_ref

        def assign_plan(self, subscriber_ref: str, profile_ref: str):
            calls.append((subscriber_ref, profile_ref))

    monkeypatch.setattr("apps.access.tasks.get_network_provider", lambda: Fake())

    assert reconcile_active_entitlements() == 0
    assert calls == []


@override_settings(NETWORK_PROVIDER="openwisp")
def test_reconcile_continues_after_network_error(paid_order, db, zone, plan_version, monkeypatch):
    from apps.citizens.models import Citizen

    first = entitlement_for_order(paid_order, starts_at=timezone.now())
    first.status = Entitlement.Status.ACTIVE
    first.save(update_fields=["status", "updated_at"])

    second_citizen = Citizen.objects.create(
        phone_e164="+221779876543", status=Citizen.Status.ACTIVE, verified_at=timezone.now()
    )
    second_order = Order.objects.create(
        citizen=second_citizen,
        plan_version=plan_version,
        zone=zone,
        amount_xof=plan_version.price_xof,
        currency="XOF",
        idempotency_key="key-2",
        status=Order.Status.PAID,
        paid_at=timezone.now(),
        expires_at=timezone.now() + timedelta(minutes=30),
    )
    second = entitlement_for_order(second_order, starts_at=timezone.now())
    second.status = Entitlement.Status.ACTIVE
    second.save(update_fields=["status", "updated_at"])

    lower, higher = sorted([first, second], key=lambda row: row.pk)

    ensure_user_calls: list[str] = []
    assign_calls: list[tuple[str, str]] = []

    class Fake:
        def ensure_user(self, subscriber_ref: str) -> str:
            ensure_user_calls.append(subscriber_ref)
            if len(ensure_user_calls) == 1:
                raise NetworkPermanentError("temporary outage")
            return subscriber_ref

        def assign_plan(self, subscriber_ref: str, profile_ref: str):
            assign_calls.append((subscriber_ref, profile_ref))

    monkeypatch.setattr("apps.access.tasks.get_network_provider", lambda: Fake())

    assert reconcile_active_entitlements() == 1
    assert ensure_user_calls == [str(lower.citizen_id), str(higher.citizen_id)]
    assert assign_calls == [(str(higher.citizen_id), plan_version.radius_profile_ref)]


@override_settings(NETWORK_PROVIDER="openwisp")
def test_reconcile_preserves_active_status_after_permanent_error(paid_order, monkeypatch):
    entitlement = entitlement_for_order(paid_order, starts_at=timezone.now())
    entitlement.status = Entitlement.Status.ACTIVE
    entitlement.save(update_fields=["status", "updated_at"])

    class Fake:
        def ensure_user(self, subscriber_ref: str) -> str:
            return subscriber_ref

        def assign_plan(self, subscriber_ref: str, profile_ref: str):
            raise NetworkPermanentError("profile missing")

    monkeypatch.setattr("apps.access.tasks.get_network_provider", lambda: Fake())

    assert reconcile_active_entitlements() == 0

    entitlement.refresh_from_db()
    assert entitlement.status == Entitlement.Status.ACTIVE


@override_settings(NETWORK_PROVIDER="openwisp")
def test_reconcile_does_not_enqueue_outbox_messages(paid_order, monkeypatch):
    entitlement = entitlement_for_order(paid_order, starts_at=timezone.now())
    entitlement.status = Entitlement.Status.ACTIVE
    entitlement.save(update_fields=["status", "updated_at"])

    class Fake:
        def ensure_user(self, subscriber_ref: str) -> str:
            return subscriber_ref

        def assign_plan(self, subscriber_ref: str, profile_ref: str):
            pass

    monkeypatch.setattr("apps.access.tasks.get_network_provider", lambda: Fake())

    before = OutboxMessage.objects.count()
    reconcile_active_entitlements()
    assert OutboxMessage.objects.count() == before
