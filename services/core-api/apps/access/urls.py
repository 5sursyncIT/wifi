from django.urls import path

from apps.access import views

urlpatterns = [
    path("portal/free-access", views.claim_free_access, name="portal-free-access"),
]
