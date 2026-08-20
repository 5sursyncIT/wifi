from django.apps import AppConfig


class IncidentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.incidents"
    verbose_name = "Incidents réseau"

    def ready(self):
        from apps.incidents import signals  # noqa: F401
