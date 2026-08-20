from django.contrib import admin

from apps.core.admin import AuditedModelAdmin
from apps.support.models import SupportTicket


@admin.register(SupportTicket)
class SupportTicketAdmin(AuditedModelAdmin):
    list_display = ("ticket_number", "category", "status", "masked_citizen", "opened_at")
    list_filter = ("status", "category")
    search_fields = ("ticket_number",)
    readonly_fields = (
        "ticket_number",
        "citizen",
        "category",
        "message",
        "order",
        "session",
        "hotspot",
        "opened_at",
        "created_at",
        "updated_at",
    )

    @admin.display(description="Usager")
    def masked_citizen(self, obj):
        return obj.citizen.masked_phone if obj.citizen_id else "—"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
