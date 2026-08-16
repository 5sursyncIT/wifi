"""Free access endpoint (cahier des charges §8.4)."""

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.access.free_access import FreeAccessRefused, grant_free_access
from apps.citizens.authentication import CitizenTokenAuthentication, citizen_of
from apps.citizens.serializers import EntitlementSerializer
from apps.portal.serializers import ErrorSerializer
from apps.portal.services import UnknownHotspot, resolve_portal_context
from apps.portal.views import _error


class FreeAccessRequestSerializer(serializers.Serializer):
    nas_id = serializers.CharField(max_length=120)


@extend_schema(
    request=FreeAccessRequestSerializer,
    responses={201: EntitlementSerializer, 400: ErrorSerializer, 404: ErrorSerializer},
    summary="Activer l'accès gratuit de la zone",
    tags=["portail"],
)
@api_view(["POST"])
@authentication_classes([CitizenTokenAuthentication])
@permission_classes([IsAuthenticated])
def claim_free_access(request: Request) -> Response:
    payload = FreeAccessRequestSerializer(data=request.data)
    payload.is_valid(raise_exception=True)

    # The zone comes from the hotspot, never from the caller (§8.2): a citizen must
    # not be able to claim the allowance of a zone they are not standing in.
    try:
        context = resolve_portal_context(nas_identifier=payload.validated_data["nas_id"])
    except UnknownHotspot:
        return _error(
            request,
            "unknown_hotspot",
            "Ce point d'accès n'est pas reconnu.",
            status.HTTP_404_NOT_FOUND,
        )

    try:
        entitlement = grant_free_access(citizen_of(request), context.zone)
    except FreeAccessRefused as error:
        return _error(request, error.reason, error.message, status.HTTP_400_BAD_REQUEST)

    return Response(EntitlementSerializer(entitlement).data, status=status.HTTP_201_CREATED)
