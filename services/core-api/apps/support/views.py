"""Support ticket endpoint (cahier des charges §8.12, §10.1)."""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.citizens.authentication import CitizenTokenAuthentication, CitizenUser
from apps.portal.serializers import ErrorSerializer
from apps.portal.services import UnknownHotspot, resolve_portal_context
from apps.portal.views import _error
from apps.support.serializers import TicketRequestSerializer, TicketSerializer
from apps.support.tickets import TicketRefused, open_ticket


def _client_ip(request):
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


@extend_schema(
    request=TicketRequestSerializer,
    responses={
        201: TicketSerializer,
        400: ErrorSerializer,
        404: ErrorSerializer,
        429: ErrorSerializer,
    },
    summary="Ouvrir un ticket de support",
    tags=["support"],
)
@api_view(["POST"])
@authentication_classes([CitizenTokenAuthentication])
@permission_classes([AllowAny])
def create_ticket(request: Request) -> Response:
    payload = TicketRequestSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    data = payload.validated_data

    hotspot = None
    nas_id = (data.get("nas_id") or "").strip()
    if nas_id:
        try:
            hotspot = resolve_portal_context(nas_identifier=nas_id).hotspot
        except UnknownHotspot:
            return _error(
                request,
                "unknown_hotspot",
                "Ce point d'accès n'est pas reconnu.",
                status.HTTP_404_NOT_FOUND,
            )

    citizen = request.user.citizen if isinstance(request.user, CitizenUser) else None
    try:
        ticket = open_ticket(
            category=data["category"],
            message=data["message"],
            citizen=citizen,
            hotspot=hotspot,
            ip_address=_client_ip(request),
        )
    except TicketRefused as error:
        http_status = (
            status.HTTP_429_TOO_MANY_REQUESTS
            if error.reason == "rate_limited"
            else status.HTTP_400_BAD_REQUEST
        )
        return _error(request, error.reason, error.message, http_status)

    return Response(TicketSerializer(ticket).data, status=status.HTTP_201_CREATED)
