from django.urls import path

from apps.support import views

urlpatterns = [
    path("support/tickets", views.create_ticket, name="support-tickets"),
]
