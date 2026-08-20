"""Settings shared by every environment.

Environment-specific modules (local, test, staging, production) import from here.
No secret may ever have a usable default: see `.env.example` at the repository root.
"""

from pathlib import Path

import environ
from corsheaders.defaults import default_headers

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
    "apps.citizens",
    "apps.messaging",
    "apps.access",
    "apps.billing",
    "apps.promotions",
    "apps.support",
    "apps.incidents",
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
CELERY_BEAT_SCHEDULE = {
    # The drain also runs on commit for latency; this beat is the recovery path for
    # when a worker died between the commit and the call (§11.2).
    "drain-outbox": {"task": "core.drain_outbox", "schedule": 30.0},
    "expire-pending-orders": {"task": "billing.expire_pending_orders", "schedule": 60.0},
    "reconcile-pending-payments": {
        "task": "billing.reconcile_pending_payments",
        "schedule": 300.0,
    },
    "reconcile-active-entitlements": {
        "task": "access.reconcile_active_entitlements",
        "schedule": 3600.0,
    },
}

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
OPENWISP_BASE_URL = env.str("OPENWISP_BASE_URL", default="https://openwisp.example.invalid")
OPENWISP_API_TOKEN = env.str("OPENWISP_API_TOKEN", default="change-me")
OPENWISP_ORGANIZATION_ID = env.str("OPENWISP_ORGANIZATION_ID", default="change-me")
OPENWISP_ORGANIZATION_SLUG = env.str("OPENWISP_ORGANIZATION_SLUG", default="ville-de-dakar")
OPENWISP_HTTP_TIMEOUT_SECONDS = env.int("OPENWISP_HTTP_TIMEOUT_SECONDS", default=10)
OPENWISP_RETRY_MAX = env.int("OPENWISP_RETRY_MAX", default=2)
OPENWISP_CIRCUIT_FAILURES = env.int("OPENWISP_CIRCUIT_FAILURES", default=5)
OPENWISP_CIRCUIT_OPEN_SECONDS = env.int("OPENWISP_CIRCUIT_OPEN_SECONDS", default=30)
SMS_PROVIDER = env.str("SMS_PROVIDER", default="mock")
PAYMENT_PROVIDER = env.str("PAYMENT_PROVIDER", default="mock")

# --- Outbox (cahier des charges §11.2) --------------------------------------

# A message that keeps failing must end up in front of an operator rather than
# retrying forever in silence.
OUTBOX_MAX_ATTEMPTS = env.int("OUTBOX_MAX_ATTEMPTS", default=10)
OUTBOX_BACKOFF_BASE_SECONDS = env.int("OUTBOX_BACKOFF_BASE_SECONDS", default=5)

# A worker can die between claiming a message and reporting its outcome. Past this
# delay a claim is presumed dead and the message is picked up again.
OUTBOX_CLAIM_TIMEOUT_SECONDS = env.int("OUTBOX_CLAIM_TIMEOUT_SECONDS", default=300)

# --- Billing (cahier des charges §8.5) --------------------------------------

ORDER_PENDING_TTL_SECONDS = env.int("ORDER_PENDING_TTL_SECONDS", default=1800)
PAYMENT_RECONCILE_AFTER_SECONDS = env.int("PAYMENT_RECONCILE_AFTER_SECONDS", default=300)

# Sentinel, not a credential: production.py refuses to start on it, exactly as for
# JWT_SIGNING_KEY.
INSECURE_WEBHOOK_SECRET_SENTINEL = "insecure-development-payment-webhook-secret"  # noqa: S105
PAYMENT_WEBHOOK_SECRET = env.str("PAYMENT_WEBHOOK_SECRET", default=INSECURE_WEBHOOK_SECRET_SENTINEL)

# --- Security ---------------------------------------------------------------

# Hosts the captive portal may redirect a browser to. Compared by exact match
# (cahier des charges §8.2): anything not listed here is dropped.
# --- Citizen sessions (cahier des charges §13.1) -----------------------------
# Sentinel, not a credential: production.py refuses to start on it. Long enough
# that HMAC-SHA256 does not warn in development.
INSECURE_JWT_KEY_SENTINEL = "insecure-development-jwt-signing-key-32b"
JWT_SIGNING_KEY = env.str("JWT_SIGNING_KEY", default=INSECURE_JWT_KEY_SENTINEL)
CITIZEN_ACCESS_TTL_SECONDS = env.int("JWT_ACCESS_TOKEN_TTL_SECONDS", default=900)
CITIZEN_REFRESH_TTL_SECONDS = env.int("JWT_REFRESH_TOKEN_TTL_SECONDS", default=1209600)

# --- OTP (cahier des charges §8.1) ------------------------------------------
# Bounds are configurable because the right values depend on real traffic and on
# the SMS budget (§22 question 16); the defaults are deliberately strict.
OTP_HASH_PEPPER = env.str("OTP_HASH_PEPPER", default="change-me")
OTP_CODE_LENGTH = env.int("OTP_CODE_LENGTH", default=6)
OTP_TTL_SECONDS = env.int("OTP_TTL_SECONDS", default=300)
OTP_WINDOW_SECONDS = env.int("OTP_WINDOW_SECONDS", default=900)
OTP_MAX_PER_PHONE = env.int("OTP_MAX_PER_PHONE", default=3)
OTP_MAX_PER_IP = env.int("OTP_MAX_PER_IP", default=10)
OTP_MAX_VERIFY_ATTEMPTS = env.int("OTP_MAX_VERIFY_ATTEMPTS", default=5)

# --- Vouchers (cahier des charges §8.6) -------------------------------------
# Dedicated pepper: a leaked OTP pepper must not unlock the voucher table.
VOUCHER_HASH_PEPPER = env.str("VOUCHER_HASH_PEPPER", default="change-me")
VOUCHER_ATTEMPT_WINDOW_SECONDS = env.int("VOUCHER_ATTEMPT_WINDOW_SECONDS", default=900)
VOUCHER_MAX_ATTEMPTS_PER_CITIZEN = env.int("VOUCHER_MAX_ATTEMPTS_PER_CITIZEN", default=10)
SUPPORT_TICKET_WINDOW_SECONDS = env.int("SUPPORT_TICKET_WINDOW_SECONDS", default=3600)
SUPPORT_TICKET_MAX_PER_WINDOW = env.int("SUPPORT_TICKET_MAX_PER_WINDOW", default=5)

PORTAL_ALLOWED_REDIRECT_HOSTS = env.list("PORTAL_ALLOWED_REDIRECT_HOSTS", default=["localhost"])

CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:3000", "http://localhost:3001"],
)
CORS_ALLOW_HEADERS = (*default_headers, "idempotency-key")
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
