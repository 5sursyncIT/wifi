"""Production: external secrets, real data, supervision and backups.

Refuses to start on an insecure configuration rather than running degraded.
"""

from django.core.exceptions import ImproperlyConfigured

from config.settings.base import *
from config.settings.base import (
    INSECURE_JWT_KEY_SENTINEL,
    INSECURE_SECRET_KEY_SENTINEL,
    INSECURE_WEBHOOK_SECRET_SENTINEL,
    JWT_SIGNING_KEY,
    PAYMENT_WEBHOOK_SECRET,
    SECRET_KEY,
    env,
)

DEBUG = False
ENVIRONMENT = "production"

if SECRET_KEY == INSECURE_SECRET_KEY_SENTINEL:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set in production.")

if JWT_SIGNING_KEY == INSECURE_JWT_KEY_SENTINEL:
    raise ImproperlyConfigured("JWT_SIGNING_KEY must be set in production.")

if PAYMENT_WEBHOOK_SECRET == INSECURE_WEBHOOK_SECRET_SENTINEL:
    raise ImproperlyConfigured("PAYMENT_WEBHOOK_SECRET must be set in production.")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS must be set in production.")

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
