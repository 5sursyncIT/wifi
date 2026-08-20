from django.contrib import admin, messages

from apps.core.admin import AuditedModelAdmin
from apps.incidents.lifecycle import acknowledge, close, resolve
from apps.incidents.models import Incident


@admin.register(Incident)
class IncidentAdmin(AuditedModelAdmin):
    list_display = (
        "incident_number",
        "priority",
        "status",
        "hotspot_label",
        "assigned_to",
        "opened_at",
    )
    list_filter = ("status", "priority", "alert_type", "source")
    search_fields = ("incident_number", "title", "hotspot__label")
    readonly_fields = (
        "incident_number",
        "opened_at",
        "acknowledged_at",
        "resolved_at",
        "created_at",
        "updated_at",
        "seconds_to_acknowledge",
        "seconds_to_resolve",
    )
    actions = ["acknowledge_selected", "resolve_selected", "close_selected"]

    @admin.display(description="Borne")
    def hotspot_label(self, obj):
        return obj.hotspot.label

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Prendre en charge")
    def acknowledge_selected(self, request, queryset):
        for incident in queryset:
            acknowledge(incident, actor=request.user)
        self.message_user(request, "Incident(s) pris en charge.", level=messages.SUCCESS)

    @admin.action(description="Marquer résolu")
    def resolve_selected(self, request, queryset):
        for incident in queryset:
            resolve(incident, actor=request.user)
        self.message_user(request, "Incident(s) résolu(s).", level=messages.SUCCESS)

    @admin.action(description="Clôturer")
    def close_selected(self, request, queryset):
        for incident in queryset:
            close(incident, actor=request.user)
        self.message_user(request, "Incident(s) clos.", level=messages.SUCCESS)
