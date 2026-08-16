"""OTP issuance, verification and abuse limits (cahier des charges §8.1, §16.1, §16.4)."""

import re
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.citizens.models import Citizen, OtpRequest
from apps.citizens.otp import (
    ConsentRequired,
    InvalidCode,
    OtpExpired,
    OtpRateLimited,
    request_otp,
    verify_otp,
)
from apps.messaging.models import SmsMessage
from apps.messaging.providers.mock import MockSmsProvider

PHONE = "+221771234567"


@pytest.fixture(autouse=True)
def clear_outbox():
    MockSmsProvider.clear()
    yield
    MockSmsProvider.clear()


def sent_code():
    """Read the code the way a citizen reads their SMS."""
    body = MockSmsProvider.outbox[-1]["body"]
    match = re.search(r"\b(\d{6})\b", body)
    assert match, f"no six-digit code in {body!r}"
    return match.group(1)


@pytest.fixture
def accepted_terms(current_terms):
    return [str(version.id) for version in current_terms]


@pytest.mark.django_db
def test_requesting_an_otp_sends_one_sms_and_records_it():
    request_otp(PHONE)

    assert len(MockSmsProvider.outbox) == 1
    assert MockSmsProvider.outbox[0]["to"] == PHONE
    message = SmsMessage.objects.get()
    assert message.purpose == SmsMessage.Purpose.OTP
    assert message.status == SmsMessage.Status.SENT


@pytest.mark.django_db
def test_the_code_is_never_stored_in_clear():
    request_otp(PHONE)

    stored = OtpRequest.objects.get()
    assert stored.code_hash != sent_code()
    assert sent_code() not in stored.code_hash


@pytest.mark.django_db
def test_verifying_the_right_code_activates_the_citizen(accepted_terms):
    request_otp(PHONE)

    citizen = verify_otp(PHONE, sent_code(), accepted_terms=accepted_terms)

    assert citizen.phone_e164 == PHONE
    assert citizen.status == Citizen.Status.ACTIVE
    assert citizen.verified_at is not None
    assert OtpRequest.objects.get().status == OtpRequest.Status.VERIFIED


@pytest.mark.django_db
def test_verification_records_the_consent_with_its_version(accepted_terms, current_terms):
    request_otp(PHONE)

    citizen = verify_otp(PHONE, sent_code(), accepted_terms=accepted_terms)

    accepted = {consent.terms_version_id for consent in citizen.consents.all()}
    assert accepted == {version.id for version in current_terms}
    assert all(consent.accepted_at is not None for consent in citizen.consents.all())


@pytest.mark.django_db
def test_verification_is_refused_without_accepting_the_current_terms(current_terms):
    request_otp(PHONE)

    with pytest.raises(ConsentRequired):
        verify_otp(PHONE, sent_code(), accepted_terms=[])

    assert not Citizen.objects.filter(phone_e164=PHONE, status=Citizen.Status.ACTIVE).exists()


@pytest.mark.django_db
def test_a_wrong_code_is_refused_and_counted(accepted_terms):
    request_otp(PHONE)

    with pytest.raises(InvalidCode):
        verify_otp(PHONE, "000000", accepted_terms=accepted_terms)

    assert OtpRequest.objects.get().attempts == 1


@pytest.mark.django_db
def test_the_code_burns_after_too_many_wrong_attempts(settings, accepted_terms):
    settings.OTP_MAX_VERIFY_ATTEMPTS = 3
    request_otp(PHONE)
    good = sent_code()

    for _ in range(3):
        with pytest.raises(InvalidCode):
            verify_otp(PHONE, "000000", accepted_terms=accepted_terms)

    # Brute force must not be rescued by eventually guessing right (§16.4).
    with pytest.raises(InvalidCode):
        verify_otp(PHONE, good, accepted_terms=accepted_terms)


@pytest.mark.django_db
def test_an_expired_code_is_refused(accepted_terms):
    request_otp(PHONE)
    stale = OtpRequest.objects.get()
    stale.expires_at = timezone.now() - timedelta(seconds=1)
    stale.save(update_fields=["expires_at"])

    with pytest.raises(OtpExpired):
        verify_otp(PHONE, sent_code(), accepted_terms=accepted_terms)


@pytest.mark.django_db
def test_a_code_cannot_be_used_twice(accepted_terms):
    request_otp(PHONE)
    code = sent_code()
    verify_otp(PHONE, code, accepted_terms=accepted_terms)

    with pytest.raises(InvalidCode):
        verify_otp(PHONE, code, accepted_terms=accepted_terms)


@pytest.mark.django_db
def test_too_many_requests_for_one_number_are_refused(settings):
    settings.OTP_MAX_PER_PHONE = 2

    request_otp(PHONE)
    request_otp(PHONE)

    with pytest.raises(OtpRateLimited):
        request_otp(PHONE)


@pytest.mark.django_db
def test_too_many_requests_from_one_address_are_refused(settings):
    settings.OTP_MAX_PER_PHONE = 50
    settings.OTP_MAX_PER_IP = 2

    request_otp("+221770000001", ip_address="41.82.0.1")
    request_otp("+221770000002", ip_address="41.82.0.1")

    # A single address enumerating numbers is the cheapest abuse there is (§8.1).
    with pytest.raises(OtpRateLimited):
        request_otp("+221770000003", ip_address="41.82.0.1")


@pytest.mark.django_db
def test_the_address_is_stored_hashed_never_in_clear():
    request_otp(PHONE, ip_address="41.82.0.1")

    stored = OtpRequest.objects.get()
    assert stored.ip_hash
    assert "41.82.0.1" not in stored.ip_hash
