"""Open, acknowledge and close incidents (cahier des charges §8.10)."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.core.audit import record_audit, snapshot
from apps.incidents.models import Incident
from apps.network.models import Hotspot

_STATUS_FOR_HOTSPOT = {
    Hotspot.Status.DOWN: (
        Incident.AlertType.EQUIPMENT_OFFLINE,
        Incident.Priority.P2,
        "Borne hors ligne",
    ),
    Hotspot.Status.DEGRADED: (
        Incident.AlertType.DEGRADED,
        Incident.Priority.P3,
        "Borne dégradée",
    ),
}


def open_incident(
    hotspot,
    *,
    priority: str,
    alert_type: str,
    source: str,
    title: str,
    actor=None,
    notes: str = "",
) -> Incident:
    existing = (
        Incident.objects.filter(
            hotspot=hotspot, alert_type=alert_type, status__in=Incident.OPEN_STATUSES
        )
        .order_by("-opened_at")
        .first()
    )
    if existing is not None:
        return existing

    with transaction.atomic():
        incident = Incident.objects.create(
            hotspot=hotspot,
            priority=priority,
            alert_type=alert_type,
            source=source,
            title=title,
            notes=notes,
        )
        record_audit(
            actor=actor,
            action="incident.open",
            target=incident,
            after=snapshot(incident),
        )
    return incident


def acknowledge(incident: Incident, *, actor) -> Incident:
    if incident.status != Incident.Status.OPEN:
        return incident
    before = snapshot(incident)
    incident.status = Incident.Status.ACKNOWLEDGED
    incident.acknowledged_at = timezone.now()
    if actor is not None and getattr(actor, "pk", None):
        incident.assigned_to = actor
    incident.save(update_fields=["status", "acknowledged_at", "assigned_to", "updated_at"])
    record_audit(
        actor=actor,
        action="incident.acknowledge",
        target=incident,
        before=before,
        after=snapshot(incident),
    )
    return incident


def resolve(incident: Incident, *, actor) -> Incident:
    if incident.status in (Incident.Status.RESOLVED, Incident.Status.CLOSED):
        return incident
    before = snapshot(incident)
    now = timezone.now()
    if incident.acknowledged_at is None:
        incident.acknowledged_at = now
    incident.status = Incident.Status.RESOLVED
    incident.resolved_at = now
    incident.save(update_fields=["status", "acknowledged_at", "resolved_at", "updated_at"])
    record_audit(
        actor=actor,
        action="incident.resolve",
        target=incident,
        before=before,
        after=snapshot(incident),
    )
    return incident


def close(incident: Incident, *, actor) -> Incident:
    if incident.status == Incident.Status.CLOSED:
        return incident
    before = snapshot(incident)
    now = timezone.now()
    incident.status = Incident.Status.CLOSED
    if incident.resolved_at is None:
        incident.resolved_at = now
    incident.save(update_fields=["status", "resolved_at", "updated_at"])
    record_audit(
        actor=actor,
        action="incident.close",
        target=incident,
        before=before,
        after=snapshot(incident),
    )
    return incident


def sync_hotspot_incidents(hotspot: Hotspot) -> Incident | None:
    """Open an incident when a hotspot is down or degraded. Never auto-closes."""
    try:
        status = Hotspot.Status(hotspot.status)
    except ValueError:
        return None
    mapping = _STATUS_FOR_HOTSPOT.get(status)
    if mapping is None:
        return None
    alert_type, priority, title = mapping
    return open_incident(
        hotspot,
        priority=priority,
        alert_type=alert_type,
        source=Incident.Source.AUTOMATIC,
        title=f"{title} — {hotspot.label}",
    )
