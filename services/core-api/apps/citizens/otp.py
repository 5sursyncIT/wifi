"""Issuing and verifying one-time codes (cahier des charges §8.1).

Codes are stored hashed with a server-side pepper, so a database dump does not hand
anyone a working code. Abuse is bounded per number *and* per address, because either
one alone is trivial to sidestep: rotating numbers defeats a per-number limit, and a
handful of phones defeats a per-address one.
"""

import hashlib
import hmac
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import get_random_string

from apps.citizens.models import Citizen, Consent, OtpRequest, TermsVersion
from apps.messaging.models import SmsMessage
from apps.messaging.providers import get_sms_provider


class OtpError(Exception):
    """Base for every OTP refusal."""


class OtpRateLimited(OtpError):
    """Too many requests for this number, address or device."""


class InvalidCode(OtpError):
    """No usable code matches what was submitted."""


class OtpExpired(OtpError):
    """The code existed but its validity window has passed."""


class ConsentRequired(OtpError):
    """The current terms have not been accepted."""


def _digest(value: str) -> str:
    """Keyed digest. The pepper lives in the environment, never in the database."""
    return hmac.new(settings.OTP_HASH_PEPPER.encode(), value.encode(), hashlib.sha256).hexdigest()


def _count_since(window_seconds: int, **filters) -> int:
    since = timezone.now() - timedelta(seconds=window_seconds)
    return OtpRequest.objects.filter(sent_at__gte=since, **filters).count()


def current_terms_versions():
    """Latest published version of each document a citizen must accept (§8.1)."""
    latest = []
    for document_type, _ in TermsVersion.Type.choices:
        version = (
            TermsVersion.objects.filter(type=document_type, published_at__lte=timezone.now())
            .order_by("-published_at")
            .first()
        )
        if version is not None:
            latest.append(version)
    return latest


@transaction.atomic
def request_otp(phone_e164, ip_address=None, device_hint=None):
    """Send a fresh code, unless this number or address has asked too often."""
    window = settings.OTP_WINDOW_SECONDS
    ip_hash = _digest(ip_address) if ip_address else ""

    if _count_since(window, phone_e164=phone_e164) >= settings.OTP_MAX_PER_PHONE:
        raise OtpRateLimited("Trop de demandes pour ce numéro. Réessayez plus tard.")

    if ip_hash and _count_since(window, ip_hash=ip_hash) >= settings.OTP_MAX_PER_IP:
        raise OtpRateLimited("Trop de demandes depuis cette connexion. Réessayez plus tard.")

    code = get_random_string(settings.OTP_CODE_LENGTH, allowed_chars="0123456789")
    otp = OtpRequest.objects.create(
        phone_e164=phone_e164,
        code_hash=_digest(code),
        ip_hash=ip_hash,
        device_hint=device_hint or "",
        expires_at=timezone.now() + timedelta(seconds=settings.OTP_TTL_SECONDS),
    )

    provider = get_sms_provider()
    minutes = settings.OTP_TTL_SECONDS // 60
    result = provider.send(
        phone_e164,
        f"Dakar WiFi : votre code est {code}. Il expire dans {minutes} minutes.",
    )
    SmsMessage.objects.create(
        provider=provider.name,
        recipient_e164=phone_e164,
        purpose=SmsMessage.Purpose.OTP,
        status=SmsMessage.Status.SENT if result.accepted else SmsMessage.Status.FAILED,
        provider_reference=result.provider_reference,
        cost_xof=result.cost_xof,
        sent_at=timezone.now() if result.accepted else None,
        failure_reason=result.failure_reason,
    )
    return otp


def _check_consents(accepted_terms):
    required = current_terms_versions()
    accepted = {str(value) for value in (accepted_terms or [])}
    missing = [version for version in required if str(version.id) not in accepted]
    if missing:
        raise ConsentRequired(
            "Les conditions d'utilisation et la politique de confidentialité "
            "doivent être acceptées."
        )
    return required


def verify_otp(phone_e164, code, accepted_terms=None):
    """Verify a code and return the activated citizen.

    Consent is checked before the code so a citizen who has not accepted the terms is
    told so without burning an attempt on their code.

    The attempt counter is committed in its own transaction *before* any refusal is
    raised. Wrapping the whole function in one atomic block would roll the counter
    back on every failure, leaving brute-force protection that counts to one forever.
    """
    required_versions = _check_consents(accepted_terms)
    now = timezone.now()

    with transaction.atomic():
        otp = (
            OtpRequest.objects.select_for_update()
            .filter(phone_e164=phone_e164, status=OtpRequest.Status.SENT)
            .order_by("-sent_at")
            .first()
        )

        if otp is None:
            outcome = "missing"
        elif otp.expires_at <= now:
            otp.status = OtpRequest.Status.EXPIRED
            otp.save(update_fields=["status"])
            outcome = "expired"
        else:
            otp.attempts += 1
            # Compared in constant time: a timing oracle would shrink the search space.
            if hmac.compare_digest(otp.code_hash, _digest(code)):
                otp.status = OtpRequest.Status.VERIFIED
                otp.verified_at = now
                otp.save(update_fields=["attempts", "status", "verified_at"])
                outcome = "verified"
            else:
                # Burning the code at the limit is what stops brute force; leaving it
                # usable would make the attempt counter decorative (§16.4).
                if otp.attempts >= settings.OTP_MAX_VERIFY_ATTEMPTS:
                    otp.status = OtpRequest.Status.FAILED
                otp.save(update_fields=["attempts", "status"])
                outcome = "invalid"

    if outcome == "expired":
        raise OtpExpired("Ce code a expiré. Demandez-en un nouveau.")
    if outcome != "verified":
        raise InvalidCode("Code incorrect.")

    return _activate(phone_e164, required_versions, now)


@transaction.atomic
def _activate(phone_e164, required_versions, now):
    citizen, _ = Citizen.objects.get_or_create(phone_e164=phone_e164)
    if citizen.status == Citizen.Status.BLOCKED:
        raise InvalidCode("Ce compte est bloqué.")

    citizen.status = Citizen.Status.ACTIVE
    citizen.verified_at = citizen.verified_at or now
    citizen.save(update_fields=["status", "verified_at"])

    for version in required_versions:
        Consent.objects.get_or_create(
            citizen=citizen,
            terms_version=version,
            defaults={"accepted_at": now, "source": "portal"},
        )

    return citizen
