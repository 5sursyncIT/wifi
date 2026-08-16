"""Record of every SMS the platform sends.

Exists so the OTP budget of §22 question 16 can be tracked, delivery disputes can be
investigated, and §13.4 has an auditable trail. The message body is never stored: it
would carry the OTP code.
"""

from django.db import models

from apps.core.models import UUIDTimeStampedModel


class SmsMessage(UUIDTimeStampedModel):
    class Purpose(models.TextChoices):
        OTP = "otp", "Code de vérification"
        NOTIFICATION = "notification", "Notification"

    class Status(models.TextChoices):
        QUEUED = "queued", "En file"
        SENT = "sent", "Envoyé"
        DELIVERED = "delivered", "Remis"
        FAILED = "failed", "Échec"

    provider = models.CharField(max_length=40)
    recipient_e164 = models.CharField(max_length=20)
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    provider_reference = models.CharField(max_length=120, blank=True)
    # Integer XOF like every amount on the platform (§1 rule 8).
    cost_xof = models.PositiveIntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["provider", "-created_at"])]
        verbose_name = "SMS"
        verbose_name_plural = "SMS"

    def __str__(self):
        return f"{self.get_purpose_display()} → {self.recipient_e164[:5]}…"
