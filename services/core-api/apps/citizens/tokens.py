"""Session tokens for citizens (cahier des charges §13.1).

Access tokens are short-lived and stateless; refresh tokens are long-lived, stored
hashed, and rotated on every use. Replaying a spent refresh token is treated as theft
rather than as a mistake, because a legitimate client never has a reason to do it.
"""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta

import jwt
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.citizens.models import Citizen, RefreshToken

ALGORITHM = "HS256"
AUDIENCE = "dakar-wifi-portal"


class InvalidToken(Exception):
    """The token is absent, malformed, expired, revoked or no longer usable."""


@dataclass(frozen=True)
class TokenPair:
    access: str
    refresh: str
    access_expires_in: int
    citizen: Citizen


def _signing_key() -> str:
    return settings.JWT_SIGNING_KEY


def _hash(token: str) -> str:
    return hmac.new(settings.JWT_SIGNING_KEY.encode(), token.encode(), hashlib.sha256).hexdigest()


def issue_tokens(citizen: Citizen) -> TokenPair:
    now = timezone.now()
    access_ttl = settings.CITIZEN_ACCESS_TTL_SECONDS

    access = jwt.encode(
        {
            "sub": str(citizen.id),
            "aud": AUDIENCE,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=access_ttl)).timestamp()),
        },
        _signing_key(),
        algorithm=ALGORITHM,
    )

    # Opaque and random: a refresh token carries no claims, it is only a lookup key.
    refresh = secrets.token_urlsafe(48)
    RefreshToken.objects.create(
        citizen=citizen,
        token_hash=_hash(refresh),
        expires_at=now + timedelta(seconds=settings.CITIZEN_REFRESH_TTL_SECONDS),
    )

    return TokenPair(access=access, refresh=refresh, access_expires_in=access_ttl, citizen=citizen)


def read_access_token(token: str):
    """Return the citizen id carried by a valid access token."""
    try:
        payload = jwt.decode(token, _signing_key(), algorithms=[ALGORITHM], audience=AUDIENCE)
    except jwt.PyJWTError as error:
        raise InvalidToken(str(error)) from error

    import uuid

    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as error:
        raise InvalidToken("Malformed subject.") from error


def rotate_refresh_token(token: str) -> TokenPair:
    """Exchange a refresh token for a fresh pair, retiring the one presented.

    The transaction must close *before* any refusal is raised: revoking a stolen
    token family inside a block that then raises would roll the revocation straight
    back, leaving the attacker's token alive.
    """
    pair = None

    with transaction.atomic():
        stored = (
            RefreshToken.objects.select_for_update()
            .select_related("citizen")
            .filter(token_hash=_hash(token))
            .first()
        )

        if stored is None:
            outcome = "Jeton inconnu."
        elif stored.revoked_at is not None:
            # A spent token coming back means a copy is circulating. Dropping the
            # whole family is the only response that ends the attacker's access too.
            revoke_all(stored.citizen)
            outcome = "Jeton déjà utilisé. Session close par sécurité."
        elif stored.expires_at <= timezone.now():
            outcome = "Jeton expiré."
        elif not stored.citizen.is_usable:
            outcome = "Compte inutilisable."
        else:
            pair = issue_tokens(stored.citizen)
            stored.revoked_at = timezone.now()
            stored.replaced_by = RefreshToken.objects.get(token_hash=_hash(pair.refresh))
            stored.save(update_fields=["revoked_at", "replaced_by"])
            outcome = ""

    if pair is None:
        raise InvalidToken(outcome)
    return pair


def revoke_all(citizen: Citizen) -> int:
    """Close every session of a citizen. Used on logout and on theft detection."""
    return RefreshToken.objects.filter(citizen=citizen, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )
