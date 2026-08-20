"""Public portal endpoints (cahier des charges §10.1)."""

import pytest
from django.utils import timezone

from apps.catalog.models import Plan, PlanVersion

CONTEXT_URL = "/api/v1/portal/context"
PLANS_URL = "/api/v1/portal/plans"


@pytest.fixture
def published_plan(zone):
    plan = Plan.objects.create(
        code="jour-1",
        name="Journée",
        description="Accès pour 24 heures",
        type=Plan.Type.PAID,
        status=Plan.Status.PUBLISHED,
    )
    plan.zones.add(zone)
    version = PlanVersion.objects.create(
        plan=plan,
        version=1,
        price_xof=1500,
        connection_seconds=86400,
        quota_total_bytes=2_000_000_000,
        bandwidth_down_kbps=4096,
        radius_profile_ref="dakar-jour",
        effective_at=timezone.now(),
    )
    plan.current_version = version
    plan.save(update_fields=["current_version"])
    return plan


@pytest.mark.django_db
def test_context_is_public_and_describes_the_resolved_zone(client, hotspot, zone, published_plan):
    response = client.get(CONTEXT_URL, {"nas_id": hotspot.nas_identifier})

    assert response.status_code == 200
    body = response.json()
    assert body["zone"]["code"] == zone.code
    assert body["fallback"]["active"] is False
    assert [plan["code"] for plan in body["plans"]] == ["jour-1"]


@pytest.mark.django_db
def test_context_labels_mock_network_and_payment_providers(client, hotspot, published_plan):
    body = client.get(CONTEXT_URL, {"nas_id": hotspot.nas_identifier}).json()

    assert body["mocks"] == {"network": True, "payment": True}


@pytest.mark.django_db
def test_context_reports_amounts_as_integers_in_xof(client, hotspot, published_plan):
    body = client.get(CONTEXT_URL, {"nas_id": hotspot.nas_identifier}).json()

    offer = body["plans"][0]
    assert offer["price_xof"] == 1500
    assert isinstance(offer["price_xof"], int)
    assert offer["currency"] == "XOF"


@pytest.mark.django_db
def test_context_exposes_the_version_identifier_needed_to_buy(client, hotspot, published_plan):
    body = client.get(CONTEXT_URL, {"nas_id": hotspot.nas_identifier}).json()

    assert body["plans"][0]["plan_version_id"] == str(published_plan.current_version_id)


@pytest.mark.django_db
def test_context_never_exposes_the_radius_profile(client, hotspot, published_plan):
    # RADIUS references belong to the network layer, never to a public payload (§8.9).
    assert (
        "dakar-jour"
        not in client.get(CONTEXT_URL, {"nas_id": hotspot.nas_identifier}).content.decode()
    )


@pytest.mark.django_db
def test_unknown_hotspot_is_rejected(client, db):
    response = client.get(CONTEXT_URL, {"nas_id": "borne-inconnue"})

    assert response.status_code == 404
    assert response.json()["code"] == "unknown_hotspot"


@pytest.mark.django_db
def test_missing_network_identifier_is_rejected(client, db):
    response = client.get(CONTEXT_URL)

    assert response.status_code == 400
    assert response.json()["code"] == "missing_nas_id"


@pytest.mark.django_db
def test_zone_claimed_in_the_query_string_is_ignored(client, hotspot, zone, published_plan):
    body = client.get(
        CONTEXT_URL, {"nas_id": hotspot.nas_identifier, "zone_id": "zone-que-je-revendique"}
    ).json()

    assert body["zone"]["code"] == zone.code


@pytest.mark.django_db
def test_redirect_url_outside_the_allowlist_is_dropped(client, hotspot, published_plan, settings):
    settings.PORTAL_ALLOWED_REDIRECT_HOSTS = ["portail.dakar.sn"]

    body = client.get(
        CONTEXT_URL,
        {"nas_id": hotspot.nas_identifier, "redirect_url": "https://attaquant.example/vol"},
    ).json()

    assert body["redirect_url"] is None


@pytest.mark.django_db
def test_redirect_url_on_an_allowed_host_is_kept(client, hotspot, published_plan, settings):
    settings.PORTAL_ALLOWED_REDIRECT_HOSTS = ["portail.dakar.sn"]

    body = client.get(
        CONTEXT_URL,
        {"nas_id": hotspot.nas_identifier, "redirect_url": "https://portail.dakar.sn/retour"},
    ).json()

    assert body["redirect_url"] == "https://portail.dakar.sn/retour"


@pytest.mark.django_db
def test_plans_endpoint_lists_the_zone_offers(client, hotspot, published_plan):
    response = client.get(PLANS_URL, {"nas_id": hotspot.nas_identifier})

    assert response.status_code == 200
    assert [plan["code"] for plan in response.json()["plans"]] == ["jour-1"]


@pytest.mark.django_db
def test_context_localizes_catalog_copy_when_lang_is_set(
    client, hotspot, zone, site, organization, published_plan
):
    zone.welcome_message = "Bienvenue sur le Wi-Fi."
    zone.i18n = {
        "en": {"label": "Independence Square", "welcome_message": "Welcome to the Wi-Fi."},
        "wo": {"welcome_message": "Dalal ak jàmm ci Wi-Fi bi."},
    }
    zone.save()
    site.i18n = {"en": {"name": "Independence Square (demonstration)"}}
    site.save()
    organization.i18n = {"en": {"name": "City of Dakar — Demonstration"}}
    organization.save()
    published_plan.i18n = {
        "en": {"name": "Day pass", "description": "24 hours of access"},
    }
    published_plan.save()

    french = client.get(CONTEXT_URL, {"nas_id": hotspot.nas_identifier}).json()
    assert french["zone"]["welcome_message"] == "Bienvenue sur le Wi-Fi."
    assert french["plans"][0]["name"] == "Journée"
    assert french["site"]["organization"] == "Ville de Dakar — Test"

    english = client.get(CONTEXT_URL, {"nas_id": hotspot.nas_identifier, "lang": "en"}).json()
    assert english["zone"]["label"] == "Independence Square"
    assert english["zone"]["welcome_message"] == "Welcome to the Wi-Fi."
    assert english["site"]["name"] == "Independence Square (demonstration)"
    assert english["site"]["organization"] == "City of Dakar — Demonstration"
    assert english["plans"][0]["name"] == "Day pass"
    assert english["plans"][0]["description"] == "24 hours of access"

    wolof = client.get(CONTEXT_URL, {"nas_id": hotspot.nas_identifier, "lang": "wo"}).json()
    assert wolof["zone"]["welcome_message"] == "Dalal ak jàmm ci Wi-Fi bi."
    assert wolof["plans"][0]["name"] == "Journée"


@pytest.mark.django_db
def test_context_honours_accept_language_when_lang_is_absent(
    client, hotspot, zone, published_plan
):
    zone.i18n = {"en": {"welcome_message": "Welcome."}}
    zone.save(update_fields=["i18n"])

    body = client.get(
        CONTEXT_URL,
        {"nas_id": hotspot.nas_identifier},
        headers={"Accept-Language": "en-GB,en;q=0.8"},
    ).json()

    assert body["zone"]["welcome_message"] == "Welcome."
