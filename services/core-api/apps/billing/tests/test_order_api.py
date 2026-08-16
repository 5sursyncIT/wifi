"""Order endpoints for the portal (§10.1, §10.4)."""

import pytest
from django.utils import timezone

from apps.billing.models import Order
from apps.billing.providers.mock import MockPaymentProvider
from apps.citizens.models import Citizen
from apps.citizens.tokens import issue_tokens

CREATE_URL = "/api/v1/orders"


@pytest.fixture(autouse=True)
def reset_provider():
    MockPaymentProvider.reset()
    yield
    MockPaymentProvider.reset()


@pytest.fixture
def auth(citizen):
    tokens = issue_tokens(citizen)
    return {"Authorization": f"Bearer {tokens.access}"}


def test_an_anonymous_caller_cannot_place_an_order(client, hotspot, plan_version):
    response = client.post(
        CREATE_URL,
        {"nas_id": hotspot.nas_identifier, "plan_version_id": str(plan_version.pk)},
        content_type="application/json",
    )

    assert response.status_code == 401


def test_placing_an_order_returns_the_push_instructions(client, auth, hotspot, plan_version):
    response = client.post(
        CREATE_URL,
        {"nas_id": hotspot.nas_identifier, "plan_version_id": str(plan_version.pk)},
        content_type="application/json",
        headers={**auth, "Idempotency-Key": "key-1"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == Order.Status.PENDING
    assert body["mode"] == "push"
    assert body["instructions"]


def test_the_idempotency_key_is_required(client, auth, hotspot, plan_version):
    response = client.post(
        CREATE_URL,
        {"nas_id": hotspot.nas_identifier, "plan_version_id": str(plan_version.pk)},
        content_type="application/json",
        headers=auth,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "idempotency_key_required"


def test_replaying_the_key_does_not_place_a_second_order(client, auth, hotspot, plan_version):
    payload = {"nas_id": hotspot.nas_identifier, "plan_version_id": str(plan_version.pk)}
    headers = {**auth, "Idempotency-Key": "key-1"}

    first = client.post(CREATE_URL, payload, content_type="application/json", headers=headers)
    second = client.post(CREATE_URL, payload, content_type="application/json", headers=headers)

    assert first.json()["id"] == second.json()["id"]
    assert Order.objects.count() == 1


def test_an_unknown_hotspot_exposes_nothing(client, auth, plan_version):
    response = client.post(
        CREATE_URL,
        {"nas_id": "inconnue", "plan_version_id": str(plan_version.pk)},
        content_type="application/json",
        headers={**auth, "Idempotency-Key": "key-1"},
    )

    assert response.status_code == 404


def test_a_citizen_reads_their_own_order(client, auth, hotspot, plan_version):
    created = client.post(
        CREATE_URL,
        {"nas_id": hotspot.nas_identifier, "plan_version_id": str(plan_version.pk)},
        content_type="application/json",
        headers={**auth, "Idempotency-Key": "key-1"},
    ).json()

    response = client.get(f"{CREATE_URL}/{created['id']}", headers=auth)

    assert response.status_code == 200
    assert response.json()["order_number"]


def test_a_citizen_cannot_read_someone_elses_order(client, auth, zone, plan_version):
    # A second citizen, because the `order` fixture belongs to the authenticated one.
    other = Citizen.objects.create(
        phone_e164="+221770000000", status=Citizen.Status.ACTIVE, verified_at=timezone.now()
    )
    theirs = Order.objects.create(
        citizen=other,
        plan_version=plan_version,
        zone=zone,
        amount_xof=plan_version.price_xof,
        currency="XOF",
        idempotency_key="key-other",
        expires_at=timezone.now() + timezone.timedelta(minutes=30),
    )

    response = client.get(f"{CREATE_URL}/{theirs.pk}", headers=auth)

    # Not 403: confirming the id exists would already leak something.
    assert response.status_code == 404
