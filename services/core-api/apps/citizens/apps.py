from django.apps import AppConfig


class CitizensConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.citizens"
    verbose_name = "Citoyens — comptes, appareils, consentements"

    def ready(self):
        # Importing registers the OpenAPI security scheme. Without it drf-spectacular
        # cannot resolve CitizenTokenAuthentication and publishes the endpoints behind
        # it as unauthenticated.
        from apps.citizens import schema  # noqa: F401
