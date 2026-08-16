"""Citizen authentication endpoints (cahier des charges §10.1, §8.1)."""

import re

import pytest

from apps.citizens.models import Citizen
from apps.messaging.providers.mock import MockSmsProvider

REQUEST_URL = "/api/v1/auth/otp/request"
VERIFY_URL = "/api/v1/auth/otp/verify"
REFRESH_URL = "/api/v1/auth/refresh"
LOGOUT_URL = "/api/v1/auth/logout"
ME_URL = "/api/v1/me"
TERMS_URL = "/api/v1/portal/terms"

PHONE = "+221771234567"


@pytest.fixture(autouse=True)
def clear_outbox():
    MockSmsProvider.clear()
    yield
    MockSmsProvider.clear()


def sent_code():
    return re.search(r"\b(\d{6})\b", MockSmsProvider.outbox[-1]["body"]).group(1)


def authenticate(client, current_terms):
    client.post(REQUEST_URL, {"phone": PHONE}, content_type="application/json")
    response = client.post(
        VERIFY_URL,
        {
            "phone": PHONE,
            "code": sent_code(),
            "accepted_terms": [str(v.id) for v in current_terms],
        },
        content_type="application/json",
    )
    return response.json()


@pytest.mark.django_db
def test_requesting_a_code_is_accepted_without_revealing_anything(client):
    response = client.post(REQUEST_URL, {"phone": PHONE}, content_type="application/json")

    assert response.status_code == 202
    # The answer must be identical whether or not the number is already known,
    # otherwise the endpoint becomes a directory of registered citizens (§13.1).
    assert response.content == b""
    assert len(MockSmsProvider.outbox) == 1


@pytest.mark.django_db
def test_the_answer_is_the_same_for_a_known_and_an_unknown_number(client, current_terms):
    authenticate(client, current_terms)
    MockSmsProvider.clear()

    known = client.post(REQUEST_URL, {"phone": PHONE}, content_type="application/json")
    unknown = client.post(REQUEST_URL, {"phone": "+221770000009"}, content_type="application/json")

    assert known.status_code == unknown.status_code == 202
    assert known.content == unknown.content == b""


@pytest.mark.django_db
def test_a_malformed_number_is_rejected(client):
    response = client.post(REQUEST_URL, {"phone": "77 123"}, content_type="application/json")

    assert response.status_code == 400
    assert MockSmsProvider.outbox == []


@pytest.mark.django_db
def test_exceeding_the_rate_limit_answers_429(client, settings):
    settings.OTP_MAX_PER_PHONE = 1
    client.post(REQUEST_URL, {"phone": PHONE}, content_type="application/json")

    response = client.post(REQUEST_URL, {"phone": PHONE}, content_type="application/json")

    assert response.status_code == 429
    assert response.json()["code"] == "otp_rate_limited"


@pytest.mark.django_db
def test_verifying_returns_a_token_pair(client, current_terms):
    body = authenticate(client, current_terms)

    assert body["access"]
    assert body["refresh"]
    assert body["citizen"]["phone_e164"] == PHONE


@pytest.mark.django_db
def test_verifying_without_consent_is_refused(client, current_terms):
    client.post(REQUEST_URL, {"phone": PHONE}, content_type="application/json")

    response = client.post(
        VERIFY_URL,
        {"phone": PHONE, "code": sent_code(), "accepted_terms": []},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["code"] == "consent_required"


@pytest.mark.django_db
def test_a_wrong_code_answers_400_with_a_stable_code(client, current_terms):
    client.post(REQUEST_URL, {"phone": PHONE}, content_type="application/json")

    response = client.post(
        VERIFY_URL,
        {
            "phone": PHONE,
            "code": "000000",
            "accepted_terms": [str(v.id) for v in current_terms],
        },
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_code"


@pytest.mark.django_db
def test_me_requires_a_token(client):
    assert client.get(ME_URL).status_code == 401


@pytest.mark.django_db
def test_me_returns_the_authenticated_citizen(client, current_terms):
    tokens = authenticate(client, current_terms)

    response = client.get(ME_URL, headers={"authorization": f"Bearer {tokens['access']}"})

    assert response.status_code == 200
    assert response.json()["phone_e164"] == PHONE


@pytest.mark.django_db
def test_a_rubbish_token_is_refused(client):
    response = client.get(ME_URL, headers={"authorization": "Bearer pas-un-jeton"})

    assert response.status_code == 401


@pytest.mark.django_db
def test_refreshing_returns_a_new_pair(client, current_terms):
    tokens = authenticate(client, current_terms)

    response = client.post(
        REFRESH_URL, {"refresh": tokens["refresh"]}, content_type="application/json"
    )

    assert response.status_code == 200
    assert response.json()["refresh"] != tokens["refresh"]


@pytest.mark.django_db
def test_logging_out_invalidates_the_refresh_token(client, current_terms):
    tokens = authenticate(client, current_terms)

    logout = client.post(
        LOGOUT_URL,
        {"refresh": tokens["refresh"]},
        content_type="application/json",
        headers={"authorization": f"Bearer {tokens['access']}"},
    )
    assert logout.status_code == 204

    replay = client.post(
        REFRESH_URL, {"refresh": tokens["refresh"]}, content_type="application/json"
    )
    assert replay.status_code == 401


@pytest.mark.django_db
def test_the_terms_to_accept_are_public(client, current_terms):
    response = client.get(TERMS_URL)

    assert response.status_code == 200
    assert len(response.json()["terms"]) == len(current_terms)


@pytest.mark.django_db
def test_a_blocked_citizen_cannot_use_their_token(client, current_terms):
    tokens = authenticate(client, current_terms)
    Citizen.objects.filter(phone_e164=PHONE).update(status=Citizen.Status.BLOCKED)

    response = client.get(ME_URL, headers={"authorization": f"Bearer {tokens['access']}"})

    assert response.status_code == 401
