"""Voucher redeem endpoint (cahier des charges §10.1)."""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.citizens.authentication import CitizenTokenAuthentication, citizen_of
from apps.citizens.serializers import EntitlementSerializer
from apps.portal.serializers import ErrorSerializer
from apps.portal.services import UnknownHotspot, resolve_portal_context
from apps.portal.views import _error
from apps.promotions.redeem import VoucherRefused, redeem_voucher
from apps.promotions.serializers import RedeemRequestSerializer


@extend_schema(
    request=RedeemRequestSerializer,
    responses={
        201: EntitlementSerializer,
        400: ErrorSerializer,
        404: ErrorSerializer,
        429: ErrorSerializer,
    },
    parameters=[
        OpenApiParameter(
            name="Idempotency-Key",
            type={"type": "string", "maxLength": 100},
            location=OpenApiParameter.HEADER,
            required=True,
            description="Clé unique de la tentative de rédemption (100 caractères maximum).",
        )
    ],
    summary="Activer un coupon",
    tags=["portail"],
)
@api_view(["POST"])
@authentication_classes([CitizenTokenAuthentication])
@permission_classes([IsAuthenticated])
def redeem(request: Request) -> Response:
    idempotency_key = request.headers.get("Idempotency-Key", "").strip()
    if not idempotency_key:
        return _error(
            request,
            "idempotency_key_required",
            "L'en-tête Idempotency-Key est obligatoire.",
            status.HTTP_400_BAD_REQUEST,
        )
    if len(idempotency_key) > 100:
        return _error(
            request,
            "invalid_idempotency_key",
            "L'en-tête Idempotency-Key ne peut pas dépasser 100 caractères.",
            status.HTTP_400_BAD_REQUEST,
        )

    payload = RedeemRequestSerializer(data=request.data)
    payload.is_valid(raise_exception=True)

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
        entitlement = redeem_voucher(
            citizen_of(request),
            payload.validated_data["code"],
            context.zone,
            idempotency_key,
        )
    except VoucherRefused as error:
        http_status = (
            status.HTTP_429_TOO_MANY_REQUESTS
            if error.reason == "rate_limited"
            else status.HTTP_400_BAD_REQUEST
        )
        return _error(request, error.reason, error.message, http_status)

    return Response(EntitlementSerializer(entitlement).data, status=status.HTTP_201_CREATED)
