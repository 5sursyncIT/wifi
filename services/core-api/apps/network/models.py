"""Network hierarchy: organisation > site > zone > hotspot (cahier des charges §8.9)."""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import UUIDTimeStampedModel


class Organization(UUIDTimeStampedModel):
    class Type(models.TextChoices):
        CITY = "city", "Ville"
        DISTRICT = "district", "Commune ou secteur"
        PARTNER = "partner", "Partenaire"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspendue"
        ARCHIVED = "archived", "Archivée"

    name = models.CharField(max_length=150, unique=True)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.CITY)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    # Name of the matching OpenWISP organization. Provisioned there, referenced here:
    # the business database never writes into OpenWISP (ADR-0001).
    openwisp_org_slug = models.SlugField(max_length=100, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "organisation"

    def __str__(self):
        return self.name


class Site(UUIDTimeStampedModel):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planifié"
        INSTALLING = "installing", "En installation"
        ACTIVE = "active", "Actif"
        DEGRADED = "degraded", "Dégradé"
        DOWN = "down", "Hors service"
        MAINTENANCE = "maintenance", "Maintenance"
        RETIRED = "retired", "Retiré"

    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="sites")
    name = models.CharField(max_length=150)
    address = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    is_public = models.BooleanField(
        default=True, help_text="Visible sur la carte publique des points d'accès."
    )
    internet_provider = models.CharField(max_length=100, blank=True)
    escalation_contact = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"], name="unique_site_name_per_organization"
            )
        ]

    def __str__(self):
        return self.name

    @property
    def has_coordinates(self):
        return self.latitude is not None and self.longitude is not None


class Zone(UUIDTimeStampedModel):
    """Access policy applied to one part of a site."""

    class AccessMode(models.TextChoices):
        FREE = "free", "Gratuit"
        PAID = "paid", "Payant"
        SPONSORED = "sponsored", "Sponsorisé"
        HYBRID = "hybrid", "Hybride"

    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspendue"
        ARCHIVED = "archived", "Archivée"

    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name="zones")
    code = models.SlugField(max_length=60, unique=True)
    label = models.CharField(max_length=150)
    access_mode = models.CharField(max_length=20, choices=AccessMode.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    # Business screens render in this timezone; storage stays UTC (§9).
    timezone = models.CharField(max_length=50, default="Africa/Dakar")
    welcome_message = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.label} ({self.code})"


class Hotspot(UUIDTimeStampedModel):
    """A gateway or access point. Its NAS identifier is what resolves a zone."""

    class Status(models.TextChoices):
        PLANNED = "planned", "Planifié"
        ACTIVE = "active", "Actif"
        DEGRADED = "degraded", "Dégradé"
        DOWN = "down", "Hors service"
        MAINTENANCE = "maintenance", "Maintenance"
        RETIRED = "retired", "Retiré"

    zone = models.ForeignKey(Zone, on_delete=models.PROTECT, related_name="hotspots")
    # The identifier the gateway presents to RADIUS. Unique platform-wide: it is the
    # only thing the portal trusts to resolve a zone (§8.2).
    nas_identifier = models.CharField(max_length=120, unique=True)
    label = models.CharField(max_length=150)
    provider = models.CharField(max_length=60, blank=True, help_text="openwrt, unifi…")
    external_id = models.CharField(
        max_length=120, blank=True, help_text="Identifiant du même équipement dans OpenWISP."
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    vendor = models.CharField(max_length=60, blank=True)
    model = models.CharField(max_length=60, blank=True)
    installed_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["nas_identifier"]

    def __str__(self):
        return f"{self.label} [{self.nas_identifier}]"
