"""Payment webhook endpoint (cahier des charges §10.2)."""

from drf_spectacular.utils import extend_schema
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.billing.webhooks import handle


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
