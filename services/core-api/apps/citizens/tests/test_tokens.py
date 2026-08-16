"""Citizen session tokens: rotation, revocation, theft detection (§13.1)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.citizens.models import Citizen, RefreshToken
from apps.citizens.tokens import (
    InvalidToken,
    issue_tokens,
    read_access_token,
    revoke_all,
    rotate_refresh_token,
)


@pytest.fixture
def citizen(db):
    return Citizen.objects.create(
        phone_e164="+221771234567", status=Citizen.Status.ACTIVE, verified_at=timezone.now()
    )


@pytest.mark.django_db
def test_an_access_token_identifies_its_citizen(citizen):
    tokens = issue_tokens(citizen)

    assert read_access_token(tokens.access) == citizen.id


@pytest.mark.django_db
def test_an_expired_access_token_is_refused(citizen, settings):
    settings.CITIZEN_ACCESS_TTL_SECONDS = -1

    tokens = issue_tokens(citizen)

    with pytest.raises(InvalidToken):
        read_access_token(tokens.access)


@pytest.mark.django_db
def test_a_tampered_access_token_is_refused(citizen):
    tokens = issue_tokens(citizen)

    with pytest.raises(InvalidToken):
        read_access_token(tokens.access[:-2] + "xy")


@pytest.mark.django_db
def test_the_refresh_token_is_never_stored_in_clear(citizen):
    tokens = issue_tokens(citizen)

    stored = RefreshToken.objects.get()
    assert stored.token_hash != tokens.refresh
    assert tokens.refresh not in stored.token_hash


@pytest.mark.django_db
def test_refreshing_returns_a_new_pair_and_retires_the_old_one(citizen):
    first = issue_tokens(citizen)

    second = rotate_refresh_token(first.refresh)

    assert second.refresh != first.refresh
    with pytest.raises(InvalidToken):
        rotate_refresh_token(first.refresh)


@pytest.mark.django_db
def test_reusing_a_retired_refresh_token_revokes_the_whole_chain(citizen):
    first = issue_tokens(citizen)
    second = rotate_refresh_token(first.refresh)

    # Replaying a spent token means someone else holds it: the safe reading is theft,
    # so every token of that citizen is dropped, not just the replayed one.
    with pytest.raises(InvalidToken):
        rotate_refresh_token(first.refresh)

    with pytest.raises(InvalidToken):
        rotate_refresh_token(second.refresh)


@pytest.mark.django_db
def test_an_expired_refresh_token_is_refused(citizen):
    tokens = issue_tokens(citizen)
    stored = RefreshToken.objects.get()
    stored.expires_at = timezone.now() - timedelta(seconds=1)
    stored.save(update_fields=["expires_at"])

    with pytest.raises(InvalidToken):
        rotate_refresh_token(tokens.refresh)


@pytest.mark.django_db
def test_logging_out_revokes_every_token_of_the_citizen(citizen):
    first = issue_tokens(citizen)
    second = issue_tokens(citizen)

    revoke_all(citizen)

    for tokens in (first, second):
        with pytest.raises(InvalidToken):
            rotate_refresh_token(tokens.refresh)


@pytest.mark.django_db
def test_a_blocked_citizen_can_no_longer_refresh(citizen):
    tokens = issue_tokens(citizen)
    citizen.status = Citizen.Status.BLOCKED
    citizen.save(update_fields=["status"])

    with pytest.raises(InvalidToken):
        rotate_refresh_token(tokens.refresh)
