"""Support tickets opened from the captive portal (cahier des charges §8.12, §9)."""

from django.db import models
from django.utils import timezone

from apps.core.models import UUIDTimeStampedModel


class SupportTicket(UUIDTimeStampedModel):
    class Category(models.TextChoices):
        CONNEXION = "connexion", "Connexion"
        OTP = "otp", "Code SMS"
        PAIEMENT = "paiement", "Paiement"
        QUOTA = "quota", "Quota"
        QUALITE = "qualite", "Qualité"
        AUTRE = "autre", "Autre"

    class Status(models.TextChoices):
        OPEN = "open", "Ouvert"
        IN_PROGRESS = "in_progress", "En cours"
        WAITING = "waiting", "En attente"
        RESOLVED = "resolved", "Résolu"
        CLOSED = "closed", "Clos"

    ticket_number = models.CharField(max_length=24, unique=True, editable=False)
    citizen = models.ForeignKey(
        "citizens.Citizen",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_tickets",
    )
    category = models.CharField(max_length=20, choices=Category.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    message = models.TextField()
    # Agent-only; never returned by the public API.
    diagnostic_notes = models.TextField(blank=True)

    order = models.ForeignKey(
        "billing.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_tickets",
    )
    session = models.ForeignKey(
        "access.NetworkSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_tickets",
    )
    hotspot = models.ForeignKey(
        "network.Hotspot",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_tickets",
    )
    opened_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-opened_at"]
        indexes = [
            models.Index(fields=["status", "-opened_at"]),
            models.Index(fields=["ticket_number"]),
        ]
        verbose_name = "ticket de support"
        verbose_name_plural = "tickets de support"

    def __str__(self):
        return self.ticket_number

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            self.ticket_number = _next_ticket_number()
        if self.status in (self.Status.RESOLVED, self.Status.CLOSED) and self.resolved_at is None:
            self.resolved_at = timezone.now()
        super().save(*args, **kwargs)


def _next_ticket_number() -> str:
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT nextval('support_ticket_number_seq')")
        value = cursor.fetchone()[0]
    return f"DW-SUP-{timezone.now():%Y%m}-{value:06d}"
