from django.apps import AppConfig


class AccessConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.access"
    verbose_name = "Accès — droits et réseau"

    def ready(self):
        # Importing registers the outbox handler. Without it, enqueue() would refuse
        # the topic and a paid activation would never be scheduled.
        from apps.access import activation  # noqa: F401
