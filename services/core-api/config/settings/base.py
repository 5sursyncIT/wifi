"""Settings shared by every environment.

Environment-specific modules (local, test, staging, production) import from here.
No secret may ever have a usable default: see `.env.example` at the repository root.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()

# Load the repository-root .env for host runs (make migrate, pytest, manage.py).
# Inside containers the variables already come from env_file and are not overwritten.
ENV_FILE = BASE_DIR.parent.parent / ".env"
if ENV_FILE.is_file():
    environ.Env.read_env(str(ENV_FILE))

# ENVIRONMENT drives which settings module manage.py loads (see manage.py).
ENVIRONMENT: str = env.str("ENVIRONMENT", default="local")

# Single source of truth for the version reported by /health and OpenAPI.
APP_VERSION = "0.1.0"

# --- Core -------------------------------------------------------------------

# Sentinel, not a credential: production.py refuses to start if it is still in place.
INSECURE_SECRET_KEY_SENTINEL = "insecure-development-key"  # noqa: S105
SECRET_KEY = env.str("DJANGO_SECRET_KEY", default=INSECURE_SECRET_KEY_SENTINEL)
DEBUG = False
ALLOWED_HOSTS: list[str] = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "apps.core",
    "apps.network",
    "apps.catalog",
    "apps.portal",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Data stores ------------------------------------------------------------

DATABASES = {
    "default": env.db_url(
        "DATABASE_URL",
        default="postgresql://dakar:dakar@localhost:5432/dakar_wifi",
    ),
}

REDIS_URL = env.str("REDIS_URL", default="redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    },
}

# --- Celery -----------------------------------------------------------------

CELERY_BROKER_URL = env.str("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env.str("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TIMEZONE = "UTC"

# --- Localisation -----------------------------------------------------------

LANGUAGE_CODE = "fr"
LANGUAGES = [("fr", "Français"), ("wo", "Wolof"), ("en", "English")]
USE_I18N = True

# Timestamps are stored in UTC; DISPLAY_TIMEZONE is what business screens render
# (cahier des charges §9).
TIME_ZONE = "UTC"
USE_TZ = True
DISPLAY_TIMEZONE = env.str("DEFAULT_TIMEZONE", default="Africa/Dakar")

# Amounts are integers in XOF, never decimals (cahier des charges §1 rule 8).
DEFAULT_CURRENCY = env.str("DEFAULT_CURRENCY", default="XOF")

# --- Static -----------------------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- REST framework ---------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Dakar WiFi — API métier",
    "DESCRIPTION": "API de la plateforme Wi-Fi public de la Ville de Dakar.",
    "VERSION": APP_VERSION,
    "OAS_VERSION": "3.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/v1",
    "COMPONENT_SPLIT_REQUEST": True,
}

# --- Adapters (mock-first, cahier des charges §1 rule 7) --------------------

NETWORK_PROVIDER = env.str("NETWORK_PROVIDER", default="mock")
SMS_PROVIDER = env.str("SMS_PROVIDER", default="mock")
PAYMENT_PROVIDER = env.str("PAYMENT_PROVIDER", default="mock")

# --- Security ---------------------------------------------------------------

# Hosts the captive portal may redirect a browser to. Compared by exact match
# (cahier des charges §8.2): anything not listed here is dropped.
PORTAL_ALLOWED_REDIRECT_HOSTS = env.list("PORTAL_ALLOWED_REDIRECT_HOSTS", default=["localhost"])

CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:3000", "http://localhost:3001"],
)
CORS_ALLOW_CREDENTIALS = True

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

# --- Logging ----------------------------------------------------------------
# Structured, no secrets, no personal data (cahier des charges §13.1).

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": env.str("LOG_LEVEL", default="INFO")},
}
