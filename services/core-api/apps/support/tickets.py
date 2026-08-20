"""Open a support ticket from the portal (cahier des charges §8.12)."""

from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
from django.db import transaction

from apps.core.audit import record_audit
from apps.support.models import SupportTicket


class TicketRefused(Exception):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


def _attempts_key(bucket: str) -> str:
    return f"support:tickets:{bucket}"


def _raise_if_rate_limited(*buckets: str) -> None:
    limit = settings.SUPPORT_TICKET_MAX_PER_WINDOW
    for bucket in buckets:
        if not bucket:
            continue
        if cache.get(_attempts_key(bucket), 0) >= limit:
            raise TicketRefused(
                "rate_limited",
                "Trop de demandes. Patientez avant d'ouvrir un autre ticket.",
            )


def _record_attempt(*buckets: str) -> None:
    window = settings.SUPPORT_TICKET_WINDOW_SECONDS
    for bucket in buckets:
        if not bucket:
            continue
        key = _attempts_key(bucket)
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=window)


def open_ticket(
    *,
    category: str,
    message: str,
    citizen=None,
    hotspot=None,
    order=None,
    session=None,
    ip_address: str = "",
) -> SupportTicket:
    buckets = [ip_address]
    if citizen is not None:
        buckets.append(str(citizen.pk))
    _raise_if_rate_limited(*buckets)

    with transaction.atomic():
        ticket = SupportTicket.objects.create(
            citizen=citizen,
            category=category,
            message=message.strip(),
            hotspot=hotspot,
            order=order,
            session=session,
        )
        record_audit(
            actor=None,
            action="ticket.create",
            target=ticket,
            after={"category": ticket.category, "source": "portal"},
        )

    _record_attempt(*buckets)
    return ticket
