import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class UUIDTimeStampedModel(models.Model):
    """Base for every business entity.

    Public identifiers are UUIDs so that sequential ids never leak volumes, and
    every row carries UTC timestamps (cahier des charges §9).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class OutboxMessage(UUIDTimeStampedModel):
    """Work that must happen outside the transaction that justified it (§11.2).

    Written in the same transaction as the state it follows from, so a crash between
    the two is impossible. The drain then talks to the outside world, where a failure
    only delays the message.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        PROCESSING = "processing", "En cours"
        DONE = "done", "Traité"
        FAILED = "failed", "Échec définitif"

    topic = models.CharField(max_length=60)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now)
    last_error = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["available_at"]
        indexes = [models.Index(fields=["status", "available_at"])]
        verbose_name = "message d'outbox"
        verbose_name_plural = "messages d'outbox"

    def __str__(self):
        return f"{self.topic} ({self.get_status_display()})"


class AuditLogQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError("AuditLog rows are append-only.")

    def delete(self):
        raise ValueError("AuditLog rows cannot be deleted.")


class AuditLog(UUIDTimeStampedModel):
    """Immutable record of a sensitive administrative action (§1 rule 12, §13.4).

    The current back-office must not be able to rewrite history. Rows are written
    once; later updates and deletes are refused both on the instance and the
    queryset so neither the admin nor a shell `QuerySet.update` can edit them.
    """

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    action = models.CharField(max_length=40)
    target_type = models.CharField(max_length=80)
    target_id = models.CharField(max_length=64)
    before_json = models.JSONField(default=dict)
    after_json = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(auto_now_add=True)

    objects = AuditLogQuerySet.as_manager()

    class Meta:
        ordering = ["-occurred_at"]
        verbose_name = "journal d'audit"
        verbose_name_plural = "journaux d'audit"
        indexes = [
            models.Index(fields=["target_type", "target_id"]),
            models.Index(fields=["occurred_at"]),
        ]

    def __str__(self):
        return f"{self.action} {self.target_type}:{self.target_id}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("AuditLog rows are append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("AuditLog rows cannot be deleted.")
