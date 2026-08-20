from django.contrib import admin

from apps.core.audit import record_audit, snapshot
from apps.core.models import AuditLog, OutboxMessage


class AuditedModelAdmin(admin.ModelAdmin):
    """Writes an AuditLog row on every create or update from the admin."""

    def save_model(self, request, obj, form, change):
        before = snapshot(type(obj).objects.filter(pk=obj.pk).first()) if change else {}
        super().save_model(request, obj, form, change)
        record_audit(
            actor=request.user,
            action="change" if change else "create",
            target=obj,
            before=before,
            after=snapshot(obj),
        )


class ImmutableFinanceAdmin(admin.ModelAdmin):
    """Financial rows are created by the API; the admin is a viewer only."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("occurred_at", "actor", "action", "target_type", "target_id")
    list_filter = ("action", "target_type")
    search_fields = ("target_id", "actor__username")
    readonly_fields = [field.name for field in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OutboxMessage)
class OutboxMessageAdmin(admin.ModelAdmin):
    list_display = ("topic", "status", "attempts", "available_at")
    list_filter = ("status", "topic")
    readonly_fields = [field.name for field in OutboxMessage._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
