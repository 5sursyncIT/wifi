"""Voucher redeem endpoint (§10.1, §16.1)."""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.access.models import Entitlement
from apps.access.providers.mock import MockNetworkProvider
from apps.citizens.tokens import issue_tokens
from apps.promotions.codes import issue_batch
from apps.promotions.models import Campaign, Sponsor, VoucherBatch

URL = "/api/v1/vouchers/redeem"


@pytest.fixture(autouse=True)
def reset_provider_and_cache():
    MockNetworkProvider.reset()
    cache.clear()
    yield
    MockNetworkProvider.reset()
    cache.clear()


@pytest.fixture
def auth(citizen):
    tokens = issue_tokens(citizen)
    return {"Authorization": f"Bearer {tokens.access}"}


@pytest.fixture
def codes(plan_version, zone):
    sponsor = Sponsor.objects.create(name="Sponsor", status=Sponsor.Status.ACTIVE)
    campaign = Campaign.objects.create(
        sponsor=sponsor,
        name="Campagne",
        start_at=timezone.now() - timedelta(days=1),
        end_at=timezone.now() + timedelta(days=30),
        status=Campaign.Status.ACTIVE,
    )
    campaign.zones.add(zone)
    batch = VoucherBatch.objects.create(
        plan_version=plan_version,
        campaign=campaign,
        zone=zone,
        quantity=1,
        max_uses=1,
        expires_at=timezone.now() + timedelta(days=7),
    )
    return issue_batch(batch)


def test_an_anonymous_caller_cannot_redeem(client, hotspot, codes):
    response = client.post(
        URL,
        {"nas_id": hotspot.nas_identifier, "code": codes[0]},
        content_type="application/json",
    )

    assert response.status_code == 401


def test_the_idempotency_key_is_required(client, auth, hotspot, codes):
    response = client.post(
        URL,
        {"nas_id": hotspot.nas_identifier, "code": codes[0]},
        content_type="application/json",
        headers=auth,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "idempotency_key_required"


def test_redeeming_a_valid_code_returns_the_right(client, auth, hotspot, codes):
    response = client.post(
        URL,
        {"nas_id": hotspot.nas_identifier, "code": codes[0]},
        content_type="application/json",
        headers={**auth, "Idempotency-Key": "key-1"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["source"] == Entitlement.Source.VOUCHER
    assert body["status"] == Entitlement.Status.ACTIVE


def test_an_unknown_hotspot_exposes_nothing(client, auth, codes):
    response = client.post(
        URL,
        {"nas_id": "inconnue", "code": codes[0]},
        content_type="application/json",
        headers={**auth, "Idempotency-Key": "key-1"},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "unknown_hotspot"


def test_a_refused_code_returns_a_stable_error(client, auth, hotspot, codes):
    response = client.post(
        URL,
        {"nas_id": hotspot.nas_identifier, "code": "NOPE-NOPE-NOPE"},
        content_type="application/json",
        headers={**auth, "Idempotency-Key": "key-1"},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "voucher_not_found"
    assert Entitlement.objects.count() == 0
