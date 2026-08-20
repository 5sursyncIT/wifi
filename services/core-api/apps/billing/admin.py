from datetime import timedelta

from django.contrib import admin, messages
from django.http import HttpResponse
from django.utils import timezone

from apps.billing.exports import payments_csv
from apps.billing.models import Order, Payment, ReconciliationRun, Refund, WebhookEvent
from apps.billing.reconciliation import run_reconciliation
from apps.billing.refunds import RefundRefused, refund_payment
from apps.core.admin import ImmutableFinanceAdmin


@admin.register(Order)
class OrderAdmin(ImmutableFinanceAdmin):
    list_display = ("order_number", "citizen", "amount_xof", "status", "created_at")
    list_filter = ("status", "reactivated_after_expiry")
    search_fields = ("order_number", "citizen__phone_e164")
    readonly_fields = ("order_number",)


@admin.register(Payment)
class PaymentAdmin(ImmutableFinanceAdmin):
    list_display = ("external_reference", "order", "provider", "mode", "status")
    list_filter = ("provider", "mode", "status")
    search_fields = ("external_reference", "order__order_number")
    actions = ["export_csv", "refund_full"]

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return request.user.has_perm("billing.view_payment")
        return False

    @admin.action(description="Exporter en CSV (sans données personnelles)")
    def export_csv(self, request, queryset):
        body = payments_csv(queryset, actor=request.user)
        response = HttpResponse(body, content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="paiements.csv"'
        return response

    @admin.action(description="Rembourser intégralement")
    def refund_full(self, request, queryset):
        for payment in queryset:
            try:
                refund_payment(payment, payment.amount_xof, "admin", request.user)
            except RefundRefused as error:
                self.message_user(request, str(error), level=messages.ERROR)
                return
        self.message_user(request, "Remboursement effectué.")


@admin.register(WebhookEvent)
class WebhookEventAdmin(ImmutableFinanceAdmin):
    list_display = ("external_event_id", "provider", "outcome", "signature_valid", "created_at")
    list_filter = ("provider", "outcome", "signature_valid")
    search_fields = ("external_event_id", "order__order_number")


@admin.register(Refund)
class RefundAdmin(ImmutableFinanceAdmin):
    list_display = ("payment", "amount_xof", "status", "requested_by", "processed_at")
    list_filter = ("status",)


@admin.register(ReconciliationRun)
class ReconciliationRunAdmin(ImmutableFinanceAdmin):
    list_display = ("provider", "period_start", "period_end", "status")
    list_filter = ("provider", "status")
    actions = ["run_last_day"]

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return request.user.has_perm("billing.view_reconciliationrun")
        return False

    @admin.action(description="Lancer un rapprochement sur les dernières 24 h")
    def run_last_day(self, request, queryset):
        end = timezone.now()
        run_reconciliation("mock", end - timedelta(hours=24), end)
        self.message_user(request, "Rapprochement enregistré.")
