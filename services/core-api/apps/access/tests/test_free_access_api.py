"""The free-access endpoint, end to end (§8.4, §17 critères 1-3)."""

import re

import pytest
from django.utils import timezone

from apps.access.models import ZoneFreePolicy
from apps.access.providers.mock import MockNetworkProvider
from apps.catalog.models import Plan, PlanVersion
from apps.messaging.providers.mock import MockSmsProvider

URL = "/api/v1/portal/free-access"
PHONE = "+221771234567"


@pytest.fixture(autouse=True)
def reset_mocks():
    MockSmsProvider.clear()
    MockNetworkProvider.reset()
    yield
    MockSmsProvider.clear()
    MockNetworkProvider.reset()


@pytest.fixture
def free_offer(zone):
    ZoneFreePolicy.objects.create(zone=zone, daily_seconds=1800, cooldown_seconds=86400)
    plan = Plan.objects.create(
        code="gratuit", name="Accès gratuit", type=Plan.Type.FREE, status=Plan.Status.PUBLISHED
    )
    plan.zones.add(zone)
    version = PlanVersion.objects.create(
        plan=plan,
        version=1,
        price_xof=0,
        connection_seconds=1800,
        radius_profile_ref="dakar-demo-gratuit",
        effective_at=timezone.now(),
    )
    plan.current_version = version
    plan.save(update_fields=["current_version"])
    return plan


def sign_in(client, current_terms):
    client.post("/api/v1/auth/otp/request", {"phone": PHONE}, content_type="application/json")
    code = re.search(r"\b(\d{6})\b", MockSmsProvider.outbox[-1]["body"]).group(1)
    body = client.post(
        "/api/v1/auth/otp/verify",
        {
            "phone": PHONE,
            "code": code,
            "accepted_terms": [str(v.id) for v in current_terms],
        },
        content_type="application/json",
    ).json()
    return {"authorization": f"Bearer {body['access']}"}


@pytest.mark.django_db
def test_a_signed_in_citizen_obtains_free_access(client, hotspot, free_offer, current_terms):
    headers = sign_in(client, current_terms)

    response = client.post(
        URL, {"nas_id": hotspot.nas_identifier}, content_type="application/json", headers=headers
    )

    assert response.status_code == 201
    assert response.json()["status"] == "active"


@pytest.mark.django_db
def test_free_access_requires_authentication(client, hotspot, free_offer):
    response = client.post(URL, {"nas_id": hotspot.nas_identifier}, content_type="application/json")

    assert response.status_code == 401


@pytest.mark.django_db
def test_an_unknown_hotspot_is_refused(client, free_offer, current_terms):
    headers = sign_in(client, current_terms)

    response = client.post(
        URL, {"nas_id": "borne-inconnue"}, content_type="application/json", headers=headers
    )

    assert response.status_code == 404
    assert response.json()["code"] == "unknown_hotspot"


@pytest.mark.django_db
def test_claiming_twice_is_refused_with_a_stable_reason(client, hotspot, free_offer, current_terms):
    headers = sign_in(client, current_terms)
    client.post(
        URL, {"nas_id": hotspot.nas_identifier}, content_type="application/json", headers=headers
    )

    response = client.post(
        URL, {"nas_id": hotspot.nas_identifier}, content_type="application/json", headers=headers
    )

    assert response.status_code == 400
    assert response.json()["code"] == "cooldown"


@pytest.mark.django_db
def test_the_right_appears_in_the_citizen_entitlements(client, hotspot, free_offer, current_terms):
    headers = sign_in(client, current_terms)
    client.post(
        URL, {"nas_id": hotspot.nas_identifier}, content_type="application/json", headers=headers
    )

    body = client.get("/api/v1/me/entitlements", headers=headers).json()

    assert [item["source"] for item in body["entitlements"]] == ["free"]
    assert body["entitlements"][0]["status"] == "active"
