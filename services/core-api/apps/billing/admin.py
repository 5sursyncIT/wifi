from django.contrib import admin

from apps.billing.models import Order, Payment, WebhookEvent


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "citizen", "amount_xof", "status", "created_at")
    list_filter = ("status", "reactivated_after_expiry")
    search_fields = ("order_number", "citizen__phone_e164")
    readonly_fields = ("order_number",)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("external_reference", "order", "provider", "mode", "status")
    list_filter = ("provider", "mode", "status")
    search_fields = ("external_reference", "order__order_number")


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("external_event_id", "provider", "outcome", "signature_valid", "created_at")
    list_filter = ("provider", "outcome", "signature_valid")
    search_fields = ("external_event_id", "order__order_number")
