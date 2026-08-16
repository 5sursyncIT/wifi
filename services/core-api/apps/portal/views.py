"""Public captive-portal endpoints.

Every response is derived from the network identifier presented by the hotspot.
Query parameters a browser could forge — a zone, a price, an offer — are never read.
"""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.network.models import Site
from apps.portal.serializers import (
    ErrorSerializer,
    PortalContextSerializer,
    PortalPlansSerializer,
    PublicSitesSerializer,
)
from apps.portal.services import UnknownHotspot, resolve_portal_context, safe_redirect_url

NAS_ID_PARAMETER = OpenApiParameter(
    name="nas_id",
    description="Identifiant réseau présenté par la borne. Seule source de vérité "
    "pour résoudre la zone.",
    required=True,
    type=str,
)
REDIRECT_PARAMETER = OpenApiParameter(
    name="redirect_url",
    description="URL de retour fournie par la passerelle. Ignorée si son hôte "
    "n'est pas explicitement autorisé.",
    required=False,
    type=str,
)


def _error(request, code, message, http_status):
    # Structured errors with a stable code and a correlation id (§10.4).
    return Response(
        {
            "code": code,
            "message": message,
            "request_id": request.headers.get("X-Request-ID", ""),
        },
        status=http_status,
    )


def _resolve(request):
    """Return (context, error_response). Exactly one of the two is None."""
    nas_id = request.query_params.get("nas_id")
    if not nas_id:
        return None, _error(
            request,
            "missing_nas_id",
            "Le paramètre nas_id est requis.",
            status.HTTP_400_BAD_REQUEST,
        )
    try:
        return resolve_portal_context(nas_identifier=nas_id), None
    except UnknownHotspot:
        # The identifier is not echoed back: an attacker probing identifiers learns
        # nothing beyond "unknown".
        return None, _error(
            request,
            "unknown_hotspot",
            "Ce point d'accès n'est pas reconnu.",
            status.HTTP_404_NOT_FOUND,
        )


@extend_schema(
    parameters=[NAS_ID_PARAMETER, REDIRECT_PARAMETER],
    responses={200: PortalContextSerializer, 400: ErrorSerializer, 404: ErrorSerializer},
    summary="Contexte du portail pour une borne",
    tags=["portail"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def portal_context(request: Request) -> Response:
    context, error = _resolve(request)
    if error is not None:
        return error

    payload = {
        "zone": context.zone,
        "site": context.zone.site,
        "fallback": {"active": context.is_fallback, "reason": context.fallback_reason},
        "plans": context.plans,
        "redirect_url": safe_redirect_url(request.query_params.get("redirect_url")),
    }
    return Response(PortalContextSerializer(payload).data)


@extend_schema(
    parameters=[NAS_ID_PARAMETER],
    responses={200: PortalPlansSerializer, 400: ErrorSerializer, 404: ErrorSerializer},
    summary="Offres disponibles pour une borne",
    tags=["portail"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def portal_plans(request: Request) -> Response:
    context, error = _resolve(request)
    if error is not None:
        return error

    return Response(PortalPlansSerializer({"plans": context.plans}).data)


@extend_schema(
    responses={200: PublicSitesSerializer},
    summary="Carte publique des points d'accès",
    tags=["portail"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def public_hotspots(request: Request) -> Response:
    """Sites the City publishes on its public map.

    Only sites explicitly marked public and actually geolocated are returned, and
    no equipment identifier ever leaves this endpoint (§8.9).
    """
    sites = (
        Site.objects.filter(is_public=True, latitude__isnull=False, longitude__isnull=False)
        .prefetch_related("zones__hotspots")
        .order_by("name")
    )

    payload = [
        {
            "name": site.name,
            "address": site.address,
            "latitude": site.latitude,
            "longitude": site.longitude,
            "status": site.status,
            "hotspot_count": sum(zone.hotspots.count() for zone in site.zones.all()),
            "access_modes": sorted({zone.access_mode for zone in site.zones.all()}),
        }
        for site in sites
    ]
    return Response(PublicSitesSerializer({"sites": payload}).data)
