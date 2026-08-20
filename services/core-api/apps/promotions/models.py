"""Sponsors, campaigns and hashed vouchers (cahier des charges §8.6, §8.11, §9)."""

from django.conf import settings
from django.db import models

from apps.catalog.models import PlanVersion
from apps.core.models import UUIDTimeStampedModel
from apps.network.models import Zone


class Sponsor(UUIDTimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        ACTIVE = "active", "Actif"
        SUSPENDED = "suspended", "Suspendu"

    name = models.CharField(max_length=150)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    contact_data = models.JSONField(default=dict, blank=True)
    partner_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sponsor",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "sponsor"
        verbose_name_plural = "sponsors"

    def __str__(self):
        return self.name


class Campaign(UUIDTimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        ACTIVE = "active", "Active"
        ENDED = "ended", "Terminée"
        CANCELLED = "cancelled", "Annulée"

    sponsor = models.ForeignKey(Sponsor, on_delete=models.PROTECT, related_name="campaigns")
    name = models.CharField(max_length=150)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    zones = models.ManyToManyField(Zone, related_name="campaigns", blank=True)
    budget_xof = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-start_at"]
        verbose_name = "campagne"
        verbose_name_plural = "campagnes"

    def __str__(self):
        return f"{self.name} ({self.sponsor})"


class VoucherBatch(UUIDTimeStampedModel):
    plan_version = models.ForeignKey(
        PlanVersion, on_delete=models.PROTECT, related_name="voucher_batches"
    )
    campaign = models.ForeignKey(
        Campaign, on_delete=models.SET_NULL, null=True, blank=True, related_name="batches"
    )
    zone = models.ForeignKey(
        Zone, on_delete=models.PROTECT, null=True, blank=True, related_name="voucher_batches"
    )
    quantity = models.PositiveIntegerField()
    max_uses = models.PositiveSmallIntegerField(default=1)
    expires_at = models.DateTimeField()
    codes_exported_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "lot de coupons"
        verbose_name_plural = "lots de coupons"

    def __str__(self):
        return f"Lot {self.quantity} x {self.plan_version}"


class Voucher(UUIDTimeStampedModel):
    class Status(models.TextChoices):
        UNUSED = "unused", "Non utilisé"
        ACTIVE = "active", "Actif"
        EXHAUSTED = "exhausted", "Épuisé"
        EXPIRED = "expired", "Expiré"
        REVOKED = "revoked", "Révoqué"

    batch = models.ForeignKey(VoucherBatch, on_delete=models.CASCADE, related_name="vouchers")
    code_hash = models.CharField(max_length=64, unique=True)
    prefix = models.CharField(max_length=4, db_index=True)
    max_uses = models.PositiveSmallIntegerField(default=1)
    uses_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNUSED)

    class Meta:
        ordering = ["prefix"]
        verbose_name = "coupon"
        verbose_name_plural = "coupons"

    def __str__(self):
        return f"{self.prefix}… ({self.get_status_display()})"


class VoucherRedemption(UUIDTimeStampedModel):
    """One successful consumption. Makes retries and double-grants a database problem."""

    voucher = models.ForeignKey(Voucher, on_delete=models.PROTECT, related_name="redemptions")
    citizen = models.ForeignKey(
        "citizens.Citizen", on_delete=models.PROTECT, related_name="voucher_redemptions"
    )
    entitlement = models.OneToOneField(
        "access.Entitlement", on_delete=models.PROTECT, related_name="voucher_redemption"
    )
    idempotency_key = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["citizen", "idempotency_key"],
                name="one_voucher_redemption_per_idempotency_key",
            ),
            models.UniqueConstraint(
                fields=["citizen", "voucher"],
                name="one_redemption_per_citizen_per_voucher",
            ),
        ]
        verbose_name = "consommation de coupon"
        verbose_name_plural = "consommations de coupons"

    def __str__(self):
        return f"{self.citizen} → {self.voucher.prefix}…"
