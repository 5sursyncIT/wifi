"""Staging: sandbox payment/SMS providers and a test OpenWISP instance."""

from config.settings.base import *

DEBUG = False
ENVIRONMENT = "staging"

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 3600
