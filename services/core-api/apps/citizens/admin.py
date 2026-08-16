from django.contrib import admin

from apps.citizens.models import (
    Citizen,
    CitizenDevice,
    Consent,
    OtpRequest,
    RefreshToken,
    TermsVersion,
)


@admin.register(Citizen)
class CitizenAdmin(admin.ModelAdmin):
    # Lists show masked numbers: a support agent browsing accounts has no business
    # reading a full directory of citizens (§13.3).
    list_display = ["masked_phone", "status", "preferred_language", "verified_at"]
    list_filter = ["status", "preferred_language"]
    search_fields = ["phone_e164", "email"]
    readonly_fields = ["verified_at", "created_at", "updated_at"]

    @admin.display(description="Téléphone")
    def masked_phone(self, obj):
        return obj.masked_phone


@admin.register(CitizenDevice)
class CitizenDeviceAdmin(admin.ModelAdmin):
    list_display = ["citizen", "label", "first_seen_at", "last_seen_at"]
    search_fields = ["citizen__phone_e164"]
    readonly_fields = ["mac_hash", "first_seen_at", "last_seen_at"]


@admin.register(TermsVersion)
class TermsVersionAdmin(admin.ModelAdmin):
    list_display = ["type", "version", "published_at", "consent_count"]
    list_filter = ["type"]

    @admin.display(description="Acceptations")
    def consent_count(self, obj):
        return obj.consents.count()


@admin.register(Consent)
class ConsentAdmin(admin.ModelAdmin):
    list_display = ["citizen", "terms_version", "accepted_at", "source"]
    list_filter = ["terms_version", "source"]
    # Legal proof: never editable, never deletable from the interface (§8.1, §13.4).
    readonly_fields = ["citizen", "terms_version", "accepted_at", "source"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OtpRequest)
class OtpRequestAdmin(admin.ModelAdmin):
    list_display = ["masked_phone", "status", "attempts", "sent_at", "verified_at"]
    list_filter = ["status"]
    # The code hash and the address hash are shown to nobody, and nothing is editable:
    # this table exists to investigate abuse, not to be corrected by hand.
    readonly_fields = [field.name for field in OtpRequest._meta.fields]

    @admin.display(description="Téléphone")
    def masked_phone(self, obj):
        return f"{obj.phone_e164[:5]}…{obj.phone_e164[-2:]}"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(RefreshToken)
class RefreshTokenAdmin(admin.ModelAdmin):
    list_display = ["citizen", "created_at", "expires_at", "revoked_at"]
    list_filter = ["revoked_at"]
    readonly_fields = [field.name for field in RefreshToken._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
