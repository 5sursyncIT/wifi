"""Citizen network sessions (cahier des charges §8.8, §10.1)."""

import pytest
from django.utils import timezone

from apps.access.activation import activate_entitlement, entitlement_for_order
from apps.access.models import NetworkSession
from apps.access.providers.mock import MockNetworkProvider
from apps.billing.models import Order
from apps.citizens.tokens import issue_tokens

SESSIONS_URL = "/api/v1/me/sessions"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def reset_provider():
    MockNetworkProvider.reset()
    yield
    MockNetworkProvider.reset()


@pytest.fixture
def auth(citizen):
    tokens = issue_tokens(citizen)
    return {"Authorization": f"Bearer {tokens.access}"}


@pytest.fixture
def paid_order(order):
    order.status = Order.Status.PAID
    order.paid_at = timezone.now()
    order.save(update_fields=["status", "paid_at"])
    return order


def test_sessions_require_a_token(client):
    assert client.get(SESSIONS_URL).status_code == 401


def test_activation_opens_a_local_session(paid_order):
    entitlement = entitlement_for_order(paid_order, starts_at=timezone.now())

    activate_entitlement({"entitlement_id": str(entitlement.pk)})

    session = NetworkSession.objects.get(entitlement=entitlement)
    assert session.citizen_id == paid_order.citizen_id
    assert session.stop_at is None
    assert session.radius_session_id == f"local-{entitlement.pk}"


def test_replaying_activation_does_not_open_a_second_session(paid_order):
    entitlement = entitlement_for_order(paid_order, starts_at=timezone.now())
    activate_entitlement({"entitlement_id": str(entitlement.pk)})
    activate_entitlement({"entitlement_id": str(entitlement.pk)})

    assert NetworkSession.objects.filter(entitlement=entitlement).count() == 1


def test_listing_sessions_returns_only_the_caller(client, auth, paid_order, citizen):
    entitlement = entitlement_for_order(paid_order, starts_at=timezone.now())
    activate_entitlement({"entitlement_id": str(entitlement.pk)})

    response = client.get(SESSIONS_URL, headers=auth)

    assert response.status_code == 200
    sessions = response.json()["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["id"] == str(NetworkSession.objects.get().pk)
    assert sessions[0]["ended_at"] is None
    assert "nas_identifier" not in sessions[0]


def test_disconnect_closes_the_session_and_is_audited(client, auth, paid_order):
    from apps.core.models import AuditLog

    entitlement = entitlement_for_order(paid_order, starts_at=timezone.now())
    activate_entitlement({"entitlement_id": str(entitlement.pk)})
    session = NetworkSession.objects.get()

    response = client.post(f"{SESSIONS_URL}/{session.pk}/disconnect", headers=auth)

    assert response.status_code == 204
    session.refresh_from_db()
    assert session.stop_at is not None
    assert AuditLog.objects.filter(action="session.disconnect", target_id=str(session.pk)).exists()


def test_disconnect_is_idempotent(client, auth, paid_order):
    entitlement = entitlement_for_order(paid_order, starts_at=timezone.now())
    activate_entitlement({"entitlement_id": str(entitlement.pk)})
    session = NetworkSession.objects.get()

    first = client.post(f"{SESSIONS_URL}/{session.pk}/disconnect", headers=auth)
    second = client.post(f"{SESSIONS_URL}/{session.pk}/disconnect", headers=auth)

    assert first.status_code == second.status_code == 204


def test_a_citizen_cannot_disconnect_someone_elses_session(client, paid_order):
    from apps.citizens.models import Citizen

    entitlement = entitlement_for_order(paid_order, starts_at=timezone.now())
    activate_entitlement({"entitlement_id": str(entitlement.pk)})
    session = NetworkSession.objects.get()
    other = Citizen.objects.create(phone_e164="+221770000001", status=Citizen.Status.ACTIVE)
    tokens = issue_tokens(other)

    response = client.post(
        f"{SESSIONS_URL}/{session.pk}/disconnect",
        headers={"Authorization": f"Bearer {tokens.access}"},
    )

    assert response.status_code == 404
    session.refresh_from_db()
    assert session.stop_at is None
