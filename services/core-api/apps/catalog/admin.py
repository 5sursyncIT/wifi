from django.contrib import admin

from apps.catalog.models import Plan, PlanVersion
from apps.core.admin import AuditedModelAdmin


class PlanVersionInline(admin.TabularInline):
    model = PlanVersion
    fk_name = "plan"
    extra = 0
    # A version never changes after creation (§8.3), so the inline is read-only:
    # editing here would raise PlanVersionIsImmutable on save.
    readonly_fields = [
        "version",
        "price_xof",
        "connection_seconds",
        "validity_seconds",
        "quota_total_bytes",
        "radius_profile_ref",
        "effective_at",
    ]
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Plan)
class PlanAdmin(AuditedModelAdmin):
    list_display = ["code", "name", "type", "status", "price", "priority", "is_visible"]
    list_filter = ["type", "status", "is_visible"]
    search_fields = ["code", "name"]
    filter_horizontal = ["zones"]
    inlines = [PlanVersionInline]

    @admin.display(description="Prix (XOF)")
    def price(self, obj):
        return obj.current_version.price_xof if obj.current_version else "—"


@admin.register(PlanVersion)
class PlanVersionAdmin(admin.ModelAdmin):
    list_display = ["plan", "version", "price_xof", "connection_seconds", "effective_at"]
    list_filter = ["plan__type"]
    search_fields = ["plan__code"]

    def get_readonly_fields(self, request, obj=None):
        # Immutable once written; still creatable.
        if obj is None:
            return []
        return [field.name for field in self.model._meta.fields]

    def has_delete_permission(self, request, obj=None):
        # Orders reference versions: deleting one would orphan what a buyer paid for.
        return False
