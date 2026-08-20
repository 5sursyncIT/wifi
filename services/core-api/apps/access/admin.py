from django.contrib import admin

from apps.access.models import Entitlement, NetworkSession, ZoneFreePolicy
from apps.core.admin import AuditedModelAdmin


@admin.register(ZoneFreePolicy)
class ZoneFreePolicyAdmin(AuditedModelAdmin):
    list_display = ["zone", "is_enabled", "daily_seconds", "cooldown_seconds", "max_devices"]
    list_filter = ["is_enabled", "zone__site__organization"]


@admin.register(Entitlement)
class EntitlementAdmin(admin.ModelAdmin):
    list_display = ["citizen", "source", "status", "zone", "starts_at", "ends_at"]
    list_filter = ["source", "status", "zone__site__organization"]
    search_fields = ["citizen__phone_e164", "radius_username"]
    # A right is the record of what someone was granted or paid for: it is corrected
    # by issuing another one, never by editing this row (§8.3, §13.4).
    readonly_fields = [
        "citizen",
        "plan_version",
        "zone",
        "source",
        "starts_at",
        "ends_at",
        "radius_username",
        "radius_synced_at",
        "activation_error",
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(NetworkSession)
class NetworkSessionAdmin(admin.ModelAdmin):
    list_display = ["citizen", "start_at", "stop_at", "bytes_in", "bytes_out"]
    list_filter = ["stop_at"]
    search_fields = ["radius_session_id", "citizen__phone_e164"]
    readonly_fields = [field.name for field in NetworkSession._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
