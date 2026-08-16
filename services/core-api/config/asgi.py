import os

from django.core.asgi import get_asgi_application

environment = os.environ.get("ENVIRONMENT", "local")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", f"config.settings.{environment}")

application = get_asgi_application()
