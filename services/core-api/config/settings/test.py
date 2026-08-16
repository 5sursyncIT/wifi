"""Isolated automated tests."""

from config.settings.base import *

DEBUG = False
ENVIRONMENT = "test"

# Celery tasks run inline so tests never need a worker.
CELERY_TASK_ALWAYS_EAGER = True

# Fast, dependency-free cache: tests must not require a live Redis.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
