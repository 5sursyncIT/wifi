from django.urls import path

from apps.messaging import views

urlpatterns = [
    path("dev/sms-outbox", views.sms_outbox, name="dev-sms-outbox"),
]
