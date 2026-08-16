from django.urls import path

from apps.billing import views

urlpatterns = [
    path("orders", views.create_order, name="order-create"),
    path("orders/<uuid:order_id>", views.order_detail, name="order-detail"),
    path("orders/<uuid:order_id>/receipt", views.order_receipt, name="order-receipt"),
    path(
        "webhooks/payments/<str:provider>",
        views.payment_webhook,
        name="payment-webhook",
    ),
]
