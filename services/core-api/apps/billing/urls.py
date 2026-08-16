from django.urls import path

from apps.billing import views

urlpatterns = [
    path(
        "webhooks/payments/<str:provider>",
        views.payment_webhook,
        name="payment-webhook",
    ),
]
