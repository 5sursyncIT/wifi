"""Local record of a network session (cahier des charges §8.8, §9).

Accounting import from RADIUS (DW-P5-04) will fill bytes later. Until then a
session is opened when a right is activated, and closed when the citizen asks
to disconnect or deletes their account.
"""

from __future__ import annotations

from django.utils import timezone

from apps.access.models import NetworkSession
from apps.access.providers import get_network_provider
from apps.access.providers.base import NetworkError
from apps.core.audit import record_audit, snapshot


class SessionNotFound(Exception):
    """The session does not exist or does not belong to the caller."""


class SessionDisconnectFailed(Exception):
    """The network layer refused or could not complete the disconnect."""

    def __init__(self, message: str, *, retryable: bool):
        super().__init__(message)
        self.retryable = retryable


def record_open_session(*, entitlement, hotspot=None) -> NetworkSession:
    session, _ = NetworkSession.objects.get_or_create(
        entitlement=entitlement,
        defaults={
            "citizen": entitlement.citizen,
            "hotspot": hotspot,
            "radius_session_id": f"local-{entitlement.pk}",
            "start_at": timezone.now(),
        },
    )
    return session


def disconnect_session(session: NetworkSession, *, citizen) -> NetworkSession:
    if session.citizen_id != citizen.pk:
        raise SessionNotFound()
    if session.stop_at is not None:
        return session

    subscriber_ref = session.citizen.radius_username or str(session.citizen_id)
    try:
        get_network_provider().disconnect(subscriber_ref)
    except NetworkError as error:
        raise SessionDisconnectFailed(str(error), retryable=error.retryable) from error

    before = snapshot(session)
    session.stop_at = timezone.now()
    session.save(update_fields=["stop_at", "updated_at"])
    record_audit(
        actor=None,
        action="session.disconnect",
        target=session,
        before=before,
        after=snapshot(session),
    )
    return session
