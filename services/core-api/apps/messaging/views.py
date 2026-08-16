"""Development helper: read what the mock SMS provider "sent".

Exists so the end-to-end tests can complete a real OTP journey. Guarded twice — by
environment *and* by the configured provider — because an endpoint that hands out
verification codes is the most dangerous thing this service could expose (§13.1).
"""

from django.conf import settings
from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.messaging.providers.mock import MockSmsProvider

ALLOWED_ENVIRONMENTS = ("local", "test")


class MockSmsSerializer(serializers.Serializer):
    to = serializers.CharField()
    body = serializers.CharField()
    reference = serializers.CharField()


class MockOutboxSerializer(serializers.Serializer):
    messages = MockSmsSerializer(many=True)


@extend_schema(exclude=True)
@api_view(["GET"])
@permission_classes([AllowAny])
def sms_outbox(request: Request) -> Response:
    if settings.ENVIRONMENT not in ALLOWED_ENVIRONMENTS or settings.SMS_PROVIDER != "mock":
        raise Http404

    return Response(MockOutboxSerializer({"messages": MockSmsProvider.outbox[-20:]}).data)
