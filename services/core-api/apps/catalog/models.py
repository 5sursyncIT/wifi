"""Offers and their immutable versions (cahier des charges §8.3)."""

from django.db import models

from apps.core.models import UUIDTimeStampedModel
from apps.network.models import Zone


class PlanVersionIsImmutable(Exception):
    """Raised when something tries to change a plan version that already exists."""


class Plan(UUIDTimeStampedModel):
    """A commercial offer.

    Carries identity, eligibility and sale rules. Everything a buyer is charged for
    or entitled to lives in PlanVersion, which never changes once created.
    """

    class Type(models.TextChoices):
        FREE = "free", "Gratuit"
        PAID = "paid", "Payant"
        SPONSORED = "sponsored", "Sponsorisé"
        HYBRID = "hybrid", "Hybride"

    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        PUBLISHED = "published", "Publié"
        SUSPENDED = "suspended", "Suspendu"
        ARCHIVED = "archived", "Archivé"

    code = models.SlugField(max_length=60, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=20, choices=Type.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    zones = models.ManyToManyField(Zone, related_name="plans", blank=True)

    # Ordering and visibility in the portal.
    priority = models.PositiveSmallIntegerField(default=100)
    is_visible = models.BooleanField(default=True)

    # Sale window; null means "no bound on that side".
    sale_starts_at = models.DateTimeField(null=True, blank=True)
    sale_ends_at = models.DateTimeField(null=True, blank=True)

    # Time-of-day window during which the offer may be used (§8.3, §8.4).
    usable_from = models.TimeField(null=True, blank=True)
    usable_until = models.TimeField(null=True, blank=True)

    renewal_policy = models.TextField(blank=True)
    refund_policy = models.TextField(blank=True)
    i18n = models.JSONField(default=dict, blank=True)

    current_version = models.OneToOneField(
        "catalog.PlanVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ["priority", "name"]
        verbose_name = "offre"
        verbose_name_plural = "offres"

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def is_sellable(self):
        return self.status == self.Status.PUBLISHED and self.current_version is not None


class PlanVersion(UUIDTimeStampedModel):
    """An immutable snapshot of a plan's price and limits.

    Orders reference a version, never a plan, so republishing an offer can never
    change what someone already bought (§8.3).
    """

    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()

    # Amounts are integers in XOF — never decimals (§1 rule 8).
    price_xof = models.PositiveIntegerField(default=0)

    # Duration of connection time granted, and how long the grant stays valid.
    connection_seconds = models.PositiveIntegerField(null=True, blank=True)
    validity_seconds = models.PositiveIntegerField(null=True, blank=True)

    # §8.3 asks for separate up and down quotas. OpenWISP enforces a combined
    # counter today (see ADR-0006), so quota_total_bytes is the one that reaches
    # RADIUS; the split values are recorded for reporting and for the day the
    # gateways can enforce them.
    quota_total_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    quota_download_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    quota_upload_bytes = models.PositiveBigIntegerField(null=True, blank=True)

    bandwidth_down_kbps = models.PositiveIntegerField(null=True, blank=True)
    bandwidth_up_kbps = models.PositiveIntegerField(null=True, blank=True)
    max_simultaneous_sessions = models.PositiveSmallIntegerField(default=1)

    # Name of a RADIUS group provisioned in OpenWISP. Referenced, never created
    # from here (ADR-0006).
    radius_profile_ref = models.CharField(max_length=120, blank=True)

    effective_at = models.DateTimeField()

    class Meta:
        ordering = ["plan", "-version"]
        constraints = [
            models.UniqueConstraint(fields=["plan", "version"], name="unique_version_per_plan")
        ]
        verbose_name = "version d'offre"
        verbose_name_plural = "versions d'offre"

    def __str__(self):
        return f"{self.plan.code} v{self.version}"

    def save(self, *args, **kwargs):
        # A version is written once. Changing a price or a quota after the fact would
        # silently rewrite what buyers already paid for; publish a new version instead.
        if not self._state.adding:
            raise PlanVersionIsImmutable(
                f"{self} already exists. Create a new version rather than editing this one."
            )
        return super().save(*args, **kwargs)
