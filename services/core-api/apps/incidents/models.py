"""Network incidents (cahier des charges §8.10, §9).

This is not an ITSM: one row per event, a status cycle, an assignee and timestamps
so acknowledgement and resolution delays can be computed. Comments live in `notes`
and in the audit log; attachments are out of the MVP.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import UUIDTimeStampedModel


class Incident(UUIDTimeStampedModel):
    class Priority(models.TextChoices):
        P1 = "p1", "P1 — critique"
        P2 = "p2", "P2 — majeur"
        P3 = "p3", "P3 — mineur"
        P4 = "p4", "P4 — faible"

    class Status(models.TextChoices):
        OPEN = "open", "Ouvert"
        ACKNOWLEDGED = "acknowledged", "Pris en charge"
        WAITING = "waiting", "En attente"
        RESOLVED = "resolved", "Résolu"
        CLOSED = "closed", "Clos"

    class Source(models.TextChoices):
        MANUAL = "manual", "Manuel"
        AUTOMATIC = "automatic", "Automatique"

    class AlertType(models.TextChoices):
        EQUIPMENT_OFFLINE = "equipment_offline", "Équipement hors ligne"
        DEGRADED = "degraded", "Dégradé"
        OTHER = "other", "Autre"

    OPEN_STATUSES = (Status.OPEN, Status.ACKNOWLEDGED, Status.WAITING)

    incident_number = models.CharField(max_length=24, unique=True, editable=False)
    hotspot = models.ForeignKey(
        "network.Hotspot", on_delete=models.PROTECT, related_name="incidents"
    )
    priority = models.CharField(max_length=4, choices=Priority.choices, default=Priority.P3)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    alert_type = models.CharField(
        max_length=30, choices=AlertType.choices, default=AlertType.OTHER
    )
    title = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_incidents",
    )
    opened_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-opened_at"]
        indexes = [
            models.Index(fields=["status", "-opened_at"]),
            models.Index(fields=["incident_number"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["hotspot", "alert_type"],
                condition=Q(status__in=["open", "acknowledged", "waiting"]),
                name="one_open_incident_per_hotspot_alert",
            )
        ]
        verbose_name = "incident"
        verbose_name_plural = "incidents"

    def __str__(self):
        return self.incident_number

    def save(self, *args, **kwargs):
        if not self.incident_number:
            self.incident_number = _next_incident_number()
        if (
            self.status in (self.Status.RESOLVED, self.Status.CLOSED)
            and self.resolved_at is None
        ):
            self.resolved_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def seconds_to_acknowledge(self) -> int | None:
        if self.acknowledged_at is None or not self.opened_at:
            return None
        return int((self.acknowledged_at - self.opened_at).total_seconds())

    @property
    def seconds_to_resolve(self) -> int | None:
        if self.resolved_at is None or not self.opened_at:
            return None
        return int((self.resolved_at - self.opened_at).total_seconds())


def _next_incident_number() -> str:
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT nextval('incidents_incident_number_seq')")
        value = cursor.fetchone()[0]
    return f"DW-INC-{timezone.now():%Y%m}-{value:06d}"
