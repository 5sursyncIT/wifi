import os

from django.core.wsgi import get_wsgi_application

environment = os.environ.get("ENVIRONMENT", "local")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", f"config.settings.{environment}")

application = get_wsgi_application()
