import uuid

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
