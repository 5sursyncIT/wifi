from django.urls import path

from apps.citizens import views

urlpatterns = [
    path("auth/otp/request", views.otp_request, name="otp-request"),
    path("auth/otp/verify", views.otp_verify, name="otp-verify"),
    path("auth/refresh", views.refresh, name="auth-refresh"),
    path("auth/logout", views.logout, name="auth-logout"),
    path("me", views.me, name="me"),
    path("me/entitlements", views.my_entitlements, name="me-entitlements"),
    path("me/export", views.me_export, name="me-export"),
    path("me/deletion", views.me_deletion, name="me-deletion"),
    path("me/sessions", views.my_sessions, name="me-sessions"),
    path(
        "me/sessions/<uuid:session_id>/disconnect",
        views.disconnect_my_session,
        name="me-session-disconnect",
    ),
    path("portal/terms", views.terms, name="portal-terms"),
]
