from django.urls import path

from apps.portal import views

urlpatterns = [
    path("portal/context", views.portal_context, name="portal-context"),
    path("portal/plans", views.portal_plans, name="portal-plans"),
    path("public/hotspots", views.public_hotspots, name="public-hotspots"),
]
