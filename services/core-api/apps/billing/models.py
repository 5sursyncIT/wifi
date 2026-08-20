"""Orders, payments and webhook deliveries (cahier des charges §8.5, §9).

Amounts are integers in XOF and are frozen on the order at creation: a later change to
the offer must never alter a purchase already made (§8.3).
"""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.catalog.models import PlanVersion
from apps.citizens.models import Citizen
from apps.core.models import UUIDTimeStampedModel
from apps.network.models import Zone


class Order(UUIDTimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        PENDING = "pending", "En attente de paiement"
        REQUIRES_ACTION = "requires_action", "Action requise"
        PAID = "paid", "Payée"
        FAILED = "failed", "Échouée"
        EXPIRED = "expired", "Expirée"
        CANCELLED = "cancelled", "Annulée"
        # Declared from the start, wired in phase 6: migrating a status field on
        # financial rows costs more than carrying two inert values.
        REFUNDED = "refunded", "Remboursée"
        PARTIALLY_REFUNDED = "partially_refunded", "Partiellement remboursée"

    order_number = models.CharField(max_length=24, unique=True, editable=False)
    citizen = models.ForeignKey(Citizen, on_delete=models.PROTECT, related_name="orders")
    plan_version = models.ForeignKey(PlanVersion, on_delete=models.PROTECT, related_name="orders")
    zone = models.ForeignKey(Zone, on_delete=models.PROTECT, related_name="orders")

    amount_xof = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="XOF")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    idempotency_key = models.CharField(max_length=100)
    expires_at = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    expired_at = models.DateTimeField(null=True, blank=True)

    # Set when a confirmation lands after the order expired (§8.5). The citizen paid,
    # so the right is granted, and the discrepancy is flagged for reconciliation.
    reactivated_after_expiry = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["citizen", "idempotency_key"], name="one_order_per_idempotency_key"
            )
        ]
        indexes = [
            models.Index(fields=["status", "expires_at"]),
            models.Index(fields=["citizen", "-created_at"]),
        ]
        verbose_name = "commande"
        verbose_name_plural = "commandes"

    def __str__(self):
        return f"{self.order_number} — {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = _next_order_number()
        super().save(*args, **kwargs)

    @property
    def is_open(self) -> bool:
        return self.status in (self.Status.DRAFT, self.Status.PENDING, self.Status.REQUIRES_ACTION)


def _next_order_number() -> str:
    """`DW-YYYYMM-NNNNNN`, the sequential part coming from a PostgreSQL sequence.

    A COUNT would let two simultaneous purchases draw the same number.
    """
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT nextval('billing_order_number_seq')")
        value = cursor.fetchone()[0]
    return f"DW-{timezone.now():%Y%m}-{value:06d}"


class Payment(UUIDTimeStampedModel):
    class Status(models.TextChoices):
        INITIATED = "initiated", "Initié"
        SUCCEEDED = "succeeded", "Réussi"
        REFUSED = "refused", "Refusé"
        EXPIRED = "expired", "Expiré"

    class Mode(models.TextChoices):
        PUSH = "push", "Push mobile"
        REDIRECT = "redirect", "Redirection"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    provider = models.CharField(max_length=40)
    mode = models.CharField(max_length=10, choices=Mode.choices)
    external_reference = models.CharField(max_length=120, db_index=True)
    redirect_url = models.CharField(max_length=500, blank=True, default="")
    amount_xof = models.PositiveIntegerField()
    fees_xof = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.INITIATED)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "paiement"
        verbose_name_plural = "paiements"

    def __str__(self):
        return f"{self.provider} {self.external_reference} ({self.get_status_display()})"


class WebhookEvent(UUIDTimeStampedModel):
    """One row per delivery — duplicates and rejections included (§8.5).

    The partial unique index is what makes a duplicate harmless: the history stays
    complete, but only one delivery per event may ever carry `processed`.
    """

    class Outcome(models.TextChoices):
        PROCESSED = "processed", "Traité"
        DUPLICATE = "duplicate", "Doublon"
        BAD_SIGNATURE = "bad_signature", "Signature invalide"
        AMOUNT_MISMATCH = "amount_mismatch", "Montant divergent"
        UNKNOWN_ORDER = "unknown_order", "Commande inconnue"
        IGNORED = "ignored", "Ignoré"

    provider = models.CharField(max_length=40)
    external_event_id = models.CharField(max_length=120)
    order = models.ForeignKey(
        Order, on_delete=models.PROTECT, null=True, blank=True, related_name="webhook_events"
    )
    signature_valid = models.BooleanField(default=False)
    outcome = models.CharField(max_length=20, choices=Outcome.choices)

    # Minimised projection, never the raw body: §9 forbids keeping a full copy that may
    # carry secrets when a reduced one is enough. The digest still lets an investigation
    # match a body against a recorded delivery.
    payload = models.JSONField(default=dict)
    body_sha256 = models.CharField(max_length=64)

    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "external_event_id"],
                condition=Q(outcome="processed"),
                name="one_processed_delivery_per_event",
            )
        ]
        indexes = [models.Index(fields=["provider", "external_event_id"])]
        verbose_name = "événement de webhook"
        verbose_name_plural = "événements de webhook"

    def __str__(self):
        return f"{self.provider} {self.external_event_id} ({self.get_outcome_display()})"


class Refund(UUIDTimeStampedModel):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Demandé"
        SUCCEEDED = "succeeded", "Réussi"
        FAILED = "failed", "Échoué"

    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="refunds")
    amount_xof = models.PositiveIntegerField()
    reason = models.CharField(max_length=200)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="requested_refunds",
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.REQUESTED)
    external_reference = models.CharField(max_length=120, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "remboursement"
        verbose_name_plural = "remboursements"

    def __str__(self):
        return f"{self.amount_xof} XOF on {self.payment.external_reference}"


class ReconciliationRun(UUIDTimeStampedModel):
    class Status(models.TextChoices):
        RUNNING = "running", "En cours"
        BALANCED = "balanced", "Équilibré"
        MISMATCH = "mismatch", "Écart"
        FAILED = "failed", "Échoué"

    provider = models.CharField(max_length=40)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.RUNNING)
    totals_json = models.JSONField(default=dict)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "rapprochement"
        verbose_name_plural = "rapprochements"

    def __str__(self):
        return f"{self.provider} {self.period_start:%Y-%m-%d} ({self.get_status_display()})"
