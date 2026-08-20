"""Export and deletion of a citizen account (cahier des charges §8.1)."""

import re

import pytest
from django.utils import timezone

from apps.access.models import Entitlement
from apps.billing.models import Order
from apps.citizens.account import delete_account, export_account
from apps.citizens.models import Citizen, CitizenDevice, Consent, RefreshToken
from apps.citizens.otp import verify_otp
from apps.citizens.tokens import issue_tokens
from apps.core.models import AuditLog
from apps.messaging.providers.mock import MockSmsProvider

EXPORT_URL = "/api/v1/me/export"
DELETE_URL = "/api/v1/me/deletion"
PHONE = "+221771234567"

pytestmark = pytest.mark.django_db


@pytest.fixture
def auth(citizen):
    tokens = issue_tokens(citizen)
    return {"Authorization": f"Bearer {tokens.access}"}


@pytest.fixture(autouse=True)
def clear_sms():
    MockSmsProvider.clear()
    yield
    MockSmsProvider.clear()


def test_export_requires_a_token(client):
    assert client.get(EXPORT_URL).status_code == 401


def test_export_returns_the_citizen_and_keeps_financial_rows(client, auth, citizen, order):
    CitizenDevice.objects.create(citizen=citizen, mac_hash="abc123")
    order.status = Order.Status.PAID
    order.paid_at = timezone.now()
    order.save(update_fields=["status", "paid_at"])

    response = client.get(EXPORT_URL, headers=auth)

    assert response.status_code == 200
    body = response.json()
    assert body["citizen"]["phone_e164"] == PHONE
    assert body["citizen"]["id"] == str(citizen.pk)
    assert body["orders"][0]["order_number"] == order.order_number
    assert body["orders"][0]["amount_xof"] == order.amount_xof
    assert body["devices"][0]["mac_hash"] == "abc123"
    assert "radius_profile_ref" not in str(body)
    assert AuditLog.objects.filter(action="citizen.export", target_id=str(citizen.pk)).exists()


def test_deletion_requires_a_token(client):
    assert client.post(DELETE_URL).status_code == 401


def test_deletion_anonymises_the_account_and_keeps_the_order(client, auth, citizen, order):
    original_phone = citizen.phone_e164
    issue_tokens(citizen)

    response = client.post(DELETE_URL, headers=auth)

    assert response.status_code == 204
    citizen.refresh_from_db()
    order.refresh_from_db()
    assert citizen.status == Citizen.Status.DELETED
    assert citizen.phone_e164 != original_phone
    assert citizen.email == ""
    assert citizen.first_name == ""
    assert citizen.last_name == ""
    assert order.citizen_id == citizen.pk
    assert order.amount_xof == 500
    assert not RefreshToken.objects.filter(citizen=citizen, revoked_at__isnull=True).exists()
    assert AuditLog.objects.filter(action="citizen.delete", target_id=str(citizen.pk)).exists()


def test_a_deleted_account_cannot_use_its_token(client, auth, citizen):
    client.post(DELETE_URL, headers=auth)

    assert client.get("/api/v1/me", headers=auth).status_code == 401


def test_the_original_number_can_open_a_new_account_after_deletion(citizen, current_terms, client):
    original_phone = citizen.phone_e164
    delete_account(citizen)

    client.post(
        "/api/v1/auth/otp/request", {"phone": original_phone}, content_type="application/json"
    )
    code = re.search(r"\b(\d{6})\b", MockSmsProvider.outbox[-1]["body"]).group(1)
    created = verify_otp(original_phone, code, accepted_terms=[v.pk for v in current_terms])

    assert created.pk != citizen.pk
    assert created.phone_e164 == original_phone
    assert created.status == Citizen.Status.ACTIVE
    citizen.refresh_from_db()
    assert citizen.status == Citizen.Status.DELETED


def test_deletion_revokes_live_entitlements(citizen, zone, plan_version):
    entitlement = Entitlement.objects.create(
        citizen=citizen,
        plan_version=plan_version,
        zone=zone,
        source=Entitlement.Source.PURCHASE,
        status=Entitlement.Status.ACTIVE,
        starts_at=timezone.now(),
    )

    delete_account(citizen)

    entitlement.refresh_from_db()
    assert entitlement.status == Entitlement.Status.REVOKED


def test_export_payload_matches_the_service(citizen, current_terms):
    Consent.objects.create(
        citizen=citizen,
        terms_version=current_terms[0],
        accepted_at=timezone.now(),
        source="portal",
    )

    payload = export_account(citizen)

    assert payload["citizen"]["phone_e164"] == citizen.phone_e164
    assert payload["consents"][0]["type"] == current_terms[0].type
    assert payload["consents"][0]["version"] == current_terms[0].version
