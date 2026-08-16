from django.conf import settings
from django.core.cache import cache
from django.db import OperationalError, connection
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.serializers import HealthSerializer


def _check_database() -> str:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except OperationalError:
        return "error"
    return "ok"


def _check_cache() -> str:
    # Redis backs the cache, Celery broker and rate limiting: any failure mode counts.
    try:
        cache.set("healthcheck", "1", timeout=5)
    except Exception:
        return "error"
    return "ok"


@extend_schema(
    responses={200: HealthSerializer, 503: HealthSerializer},
    summary="État de santé du service",
    tags=["health"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request: Request) -> Response:
    """Liveness and readiness probe."""
    checks = {"database": _check_database(), "cache": _check_cache()}
    healthy = all(state == "ok" for state in checks.values())
    return Response(
        {
            "status": "ok" if healthy else "unavailable",
            "environment": settings.ENVIRONMENT,
            "version": settings.APP_VERSION,
            "checks": checks,
        },
        status=200 if healthy else 503,
    )
