"""Order and payment endpoints (cahier des charges §10)."""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.billing.models import Order
from apps.billing.orders import OrderRefused, place_order
from apps.billing.serializers import OrderRequestSerializer, OrderSerializer, ReceiptSerializer
from apps.billing.webhooks import handle
from apps.catalog.models import PlanVersion
from apps.citizens.authentication import CitizenTokenAuthentication, citizen_of
from apps.portal.serializers import ErrorSerializer
from apps.portal.services import UnknownHotspot, resolve_portal_context
from apps.portal.views import _error


@extend_schema(
    request=OrderRequestSerializer,
    responses={201: OrderSerializer, 400: ErrorSerializer, 404: ErrorSerializer},
    summary="Commander une offre payante",
    tags=["commandes"],
)
@api_view(["POST"])
@authentication_classes([CitizenTokenAuthentication])
@permission_classes([IsAuthenticated])
def create_order(request: Request) -> Response:
    idempotency_key = request.headers.get("Idempotency-Key", "").strip()
    if not idempotency_key:
        return _error(
            request,
            "idempotency_key_required",
            "L'en-tête Idempotency-Key est obligatoire.",
            status.HTTP_400_BAD_REQUEST,
        )

    payload = OrderRequestSerializer(data=request.data)
    payload.is_valid(raise_exception=True)

    # The zone comes from the hotspot, never from the caller (§8.2).
    try:
        context = resolve_portal_context(nas_identifier=payload.validated_data["nas_id"])
    except UnknownHotspot:
        return _error(
            request,
            "unknown_hotspot",
            "Ce point d'accès n'est pas reconnu.",
            status.HTTP_404_NOT_FOUND,
        )

    version = PlanVersion.objects.filter(pk=payload.validated_data["plan_version_id"]).first()
    if version is None:
        return _error(
            request,
            "unknown_offer",
            "Cette offre n'existe pas.",
            status.HTTP_404_NOT_FOUND,
        )

    try:
        order, payment = place_order(citizen_of(request), context.zone, version, idempotency_key)
    except OrderRefused as error:
        return _error(request, error.reason, error.message, status.HTTP_400_BAD_REQUEST)

    data = OrderSerializer(order).data
    mode = payment.mode if payment is not None else ""
    data["mode"] = mode
    data["instructions"] = "Validez le paiement sur votre téléphone." if mode == "push" else ""
    return Response(data, status=status.HTTP_201_CREATED)


@extend_schema(
    responses={200: OrderSerializer, 404: ErrorSerializer},
    summary="Statut d'une commande",
    tags=["commandes"],
)
@api_view(["GET"])
@authentication_classes([CitizenTokenAuthentication])
@permission_classes([IsAuthenticated])
def order_detail(request: Request, order_id) -> Response:
    # Filtered on the authenticated citizen, never on the id alone.
    order = Order.objects.filter(pk=order_id, citizen=citizen_of(request)).first()
    if order is None:
        return _error(
            request,
            "unknown_order",
            "Cette commande n'existe pas.",
            status.HTTP_404_NOT_FOUND,
        )
    return Response(OrderSerializer(order).data)


@extend_schema(
    responses={200: ReceiptSerializer, 404: ErrorSerializer},
    summary="Reçu d'une commande payée",
    tags=["commandes"],
)
@api_view(["GET"])
@authentication_classes([CitizenTokenAuthentication])
@permission_classes([IsAuthenticated])
def order_receipt(request: Request, order_id) -> Response:
    order = (
        Order.objects.filter(
            pk=order_id,
            citizen=citizen_of(request),
            status=Order.Status.PAID,
        )
        .select_related("plan_version__plan")
        .first()
    )
    if order is None:
        return _error(
            request,
            "unknown_order",
            "Aucun reçu pour cette commande.",
            status.HTTP_404_NOT_FOUND,
        )
    return Response(ReceiptSerializer(order).data)


@extend_schema(
    request=None,
    responses={200: None, 400: None, 404: None},
    auth=[],
    summary="Webhook de paiement",
    tags=["webhooks"],
)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def payment_webhook(request: Request, provider: str) -> Response:
    # Read the raw body before anything touches request.data: the signature covers the
    # exact bytes the provider sent, and a parsed-then-reserialised copy is not them.
    body = request.body
    result = handle(provider, request.headers, body)
    return Response({"outcome": result.outcome}, status=result.http_status)
