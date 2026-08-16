import os

from celery import Celery

environment = os.environ.get("ENVIRONMENT", "local")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", f"config.settings.{environment}")

app = Celery("dakar_wifi")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
