"""Access rights and the zone rules that govern free allocation (§8.4, §8.7)."""

from django.db import models

from apps.catalog.models import PlanVersion
from apps.citizens.models import Citizen
from apps.core.models import UUIDTimeStampedModel
from apps.network.models import Zone


class ZoneFreePolicy(UUIDTimeStampedModel):
    """Free-access rules for one zone.

    Enforced server-side and mirrored into RADIUS: checking only in the interface
    would leave the allowance open to anyone talking to the API directly (§8.4).
    """

    zone = models.OneToOneField(Zone, on_delete=models.CASCADE, related_name="free_policy")
    is_enabled = models.BooleanField(default=True)

    daily_seconds = models.PositiveIntegerField(
        default=1800, help_text="Temps offert par période, en secondes."
    )
    daily_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    max_session_seconds = models.PositiveIntegerField(null=True, blank=True)

    # Delay before the same citizen may be granted free access again (§8.4).
    cooldown_seconds = models.PositiveIntegerField(default=86400)
    max_devices = models.PositiveSmallIntegerField(default=2)

    # Optional time-of-day window; both null means "any time".
    usable_from = models.TimeField(null=True, blank=True)
    usable_until = models.TimeField(null=True, blank=True)

    class Meta:
        verbose_name = "politique d'accès gratuit"
        verbose_name_plural = "politiques d'accès gratuit"

    def __str__(self):
        return f"Accès gratuit — {self.zone}"


class Entitlement(UUIDTimeStampedModel):
    """A right of access held by a citizen (§8.7).

    Always points at an immutable PlanVersion, never at a Plan, so a later change to
    the offer cannot alter a right already granted (§8.3).
    """

    class Source(models.TextChoices):
        FREE = "free", "Attribution gratuite"
        PURCHASE = "purchase", "Achat"
        VOUCHER = "voucher", "Coupon"
        SPONSOR = "sponsor", "Sponsor"

    class Status(models.TextChoices):
        PENDING_ACTIVATION = "pending_activation", "En attente d'activation"
        ACTIVE = "active", "Actif"
        EXHAUSTED = "exhausted", "Épuisé"
        EXPIRED = "expired", "Expiré"
        SUSPENDED = "suspended", "Suspendu"
        REVOKED = "revoked", "Révoqué"
        ACTIVATION_FAILED = "activation_failed", "Échec d'activation"

    citizen = models.ForeignKey(Citizen, on_delete=models.PROTECT, related_name="entitlements")
    plan_version = models.ForeignKey(
        PlanVersion, on_delete=models.PROTECT, related_name="entitlements"
    )
    zone = models.ForeignKey(Zone, on_delete=models.PROTECT, related_name="entitlements")

    # One entitlement per order, enforced by the database: "activation du forfait une
    # seule fois" (§8.5) must not depend on application logic getting concurrency right.
    order = models.OneToOneField(
        "billing.Order",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="entitlement",
    )

    source = models.CharField(max_length=20, choices=Source.choices)
    status = models.CharField(
        max_length=25, choices=Status.choices, default=Status.PENDING_ACTIVATION
    )

    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)

    # Link to the RADIUS identity (the `RadiusBinding` concept of §9). Kept on the
    # entitlement while a single binding per right is enough; the outbox of §11.2
    # arrives with payments in phase 4.
    radius_username = models.CharField(max_length=120, blank=True)
    radius_synced_at = models.DateTimeField(null=True, blank=True)
    activation_error = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["citizen", "-created_at"]),
            models.Index(fields=["status"]),
        ]
        verbose_name = "droit d'accès"
        verbose_name_plural = "droits d'accès"

    def __str__(self):
        return f"{self.get_source_display()} — {self.citizen} ({self.get_status_display()})"

    @property
    def is_live(self):
        return self.status == self.Status.ACTIVE
