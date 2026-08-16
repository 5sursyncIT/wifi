"""Citizen accounts, devices, consents and OTP attempts (cahier des charges §8.1, §9).

A citizen is not a Django user: see ADR-0007. They authenticate by phone and OTP,
hold no password and never reach the administration.
"""

from django.db import models
from django.utils import timezone

from apps.core.models import UUIDTimeStampedModel


class Citizen(UUIDTimeStampedModel):
    """The `User` concept of §9, named to avoid confusion with `auth.User`."""

    class Status(models.TextChoices):
        PENDING = "pending", "En attente de vérification"
        ACTIVE = "active", "Actif"
        BLOCKED = "blocked", "Bloqué"
        DELETED = "deleted", "Supprimé"

    class Language(models.TextChoices):
        FR = "fr", "Français"
        WO = "wo", "Wolof"
        EN = "en", "English"

    # Normalised international format, the only identity the citizen supplies (§8.1).
    phone_e164 = models.CharField(max_length=20, unique=True)
    email = models.EmailField(blank=True)
    first_name = models.CharField(max_length=80, blank=True)
    last_name = models.CharField(max_length=80, blank=True)
    preferred_language = models.CharField(
        max_length=5, choices=Language.choices, default=Language.FR
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    verified_at = models.DateTimeField(null=True, blank=True)

    # Reference to the matching RADIUS user, created by the network adapter after
    # verification. Never written to OpenWISP from here (ADR-0001).
    radius_username = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "citoyen"
        indexes = [models.Index(fields=["status"])]

    def __str__(self):
        return self.masked_phone

    @property
    def masked_phone(self):
        """Phone number safe to show in a back-office list or a log line (§13.1)."""
        return f"{self.phone_e164[:5]}…{self.phone_e164[-2:]}" if self.phone_e164 else ""

    @property
    def is_usable(self):
        return self.status == self.Status.ACTIVE


class CitizenDevice(UUIDTimeStampedModel):
    """A device a citizen has connected from.

    Android and iOS randomise MAC addresses per network and may rotate them, so this
    is a convenience signal only — never an authorisation (§8.1). The address itself
    is stored hashed and never in clear.
    """

    citizen = models.ForeignKey(Citizen, on_delete=models.CASCADE, related_name="devices")
    mac_hash = models.CharField(max_length=64)
    label = models.CharField(max_length=80, blank=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    trusted_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_seen_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["citizen", "mac_hash"], name="unique_device_per_citizen"
            )
        ]

    def __str__(self):
        return f"{self.label or 'appareil'} de {self.citizen}"


class TermsVersion(UUIDTimeStampedModel):
    """A published version of the terms or the privacy policy (§8.1)."""

    class Type(models.TextChoices):
        TERMS = "terms", "Conditions d'utilisation"
        PRIVACY = "privacy", "Politique de confidentialité"

    type = models.CharField(max_length=20, choices=Type.choices)
    version = models.CharField(max_length=20)
    content_url = models.URLField(blank=True)
    summary = models.TextField(blank=True)
    published_at = models.DateTimeField()

    class Meta:
        ordering = ["type", "-published_at"]
        constraints = [
            models.UniqueConstraint(fields=["type", "version"], name="unique_terms_version")
        ]
        verbose_name = "version des conditions"
        verbose_name_plural = "versions des conditions"

    def __str__(self):
        return f"{self.get_type_display()} v{self.version}"


class Consent(UUIDTimeStampedModel):
    """Proof that a citizen accepted a precise version, at a precise time (§8.1)."""

    citizen = models.ForeignKey(Citizen, on_delete=models.CASCADE, related_name="consents")
    terms_version = models.ForeignKey(
        TermsVersion, on_delete=models.PROTECT, related_name="consents"
    )
    accepted_at = models.DateTimeField()
    source = models.CharField(max_length=40, default="portal")

    class Meta:
        ordering = ["-accepted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["citizen", "terms_version"], name="unique_consent_per_version"
            )
        ]
        verbose_name = "consentement"

    def __str__(self):
        return f"{self.citizen} — {self.terms_version}"


class OtpRequest(UUIDTimeStampedModel):
    """One OTP send attempt.

    Kept as a record rather than a cache entry because §8.1 requires abuse limits per
    number, address, device and period, and §13.4 requires the trail to be auditable.
    The code itself is only ever stored hashed.
    """

    class Status(models.TextChoices):
        SENT = "sent", "Envoyé"
        VERIFIED = "verified", "Vérifié"
        EXPIRED = "expired", "Expiré"
        FAILED = "failed", "Échec de vérification"

    phone_e164 = models.CharField(max_length=20)
    code_hash = models.CharField(max_length=64)
    # Hashed so a log or an export never carries a raw address (§13.3).
    ip_hash = models.CharField(max_length=64, blank=True)
    device_hint = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SENT)
    attempts = models.PositiveSmallIntegerField(default=0)
    sent_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-sent_at"]
        indexes = [
            models.Index(fields=["phone_e164", "-sent_at"]),
            models.Index(fields=["ip_hash", "-sent_at"]),
        ]
        verbose_name = "demande OTP"
        verbose_name_plural = "demandes OTP"

    def __str__(self):
        return f"OTP {self.phone_e164[:5]}… ({self.get_status_display()})"


class RefreshToken(UUIDTimeStampedModel):
    """A citizen's long-lived credential, stored hashed.

    Rotation leaves a trail (`replaced_by`) so that replaying a spent token can be
    detected: that only happens when someone other than the citizen holds it (§13.1).
    """

    citizen = models.ForeignKey(Citizen, on_delete=models.CASCADE, related_name="refresh_tokens")
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    replaced_by = models.OneToOneField(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="replaces"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["citizen", "-created_at"])]
        verbose_name = "jeton de rafraîchissement"
        verbose_name_plural = "jetons de rafraîchissement"

    def __str__(self):
        return f"jeton de {self.citizen}"

    @property
    def is_usable(self):
        return self.revoked_at is None and self.expires_at > timezone.now()
