"""Citizen authentication and account endpoints (cahier des charges §10.1)."""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.access.models import NetworkSession
from apps.access.sessions import SessionDisconnectFailed, SessionNotFound, disconnect_session
from apps.citizens.account import delete_account, export_account
from apps.citizens.authentication import CitizenTokenAuthentication, citizen_of
from apps.citizens.otp import (
    ConsentRequired,
    InvalidCode,
    OtpExpired,
    OtpRateLimited,
    current_terms_versions,
    request_otp,
    verify_otp,
)
from apps.citizens.serializers import (
    AccountExportSerializer,
    CitizenSerializer,
    EntitlementListSerializer,
    OtpRequestSerializer,
    OtpVerifySerializer,
    RefreshSerializer,
    SessionListSerializer,
    TermsListSerializer,
    TokenPairSerializer,
)
from apps.citizens.tokens import InvalidToken, issue_tokens, revoke_all, rotate_refresh_token
from apps.portal.serializers import ErrorSerializer
from apps.portal.views import _error

citizen_auth = authentication_classes([CitizenTokenAuthentication])


def _client_ip(request):
    # Behind nginx the real address arrives in X-Forwarded-For; the left-most entry
    # is the client. Trusting it requires the proxy to overwrite the header, which
    # the deployment documents (§15.2).
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


@extend_schema(
    request=OtpRequestSerializer,
    responses={202: None, 400: ErrorSerializer, 429: ErrorSerializer},
    summary="Demander un code de vérification",
    tags=["authentification"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
def otp_request(request: Request) -> Response:
    payload = OtpRequestSerializer(data=request.data)
    payload.is_valid(raise_exception=True)

    try:
        request_otp(payload.validated_data["phone"], ip_address=_client_ip(request))
    except OtpRateLimited as error:
        return _error(request, "otp_rate_limited", str(error), status.HTTP_429_TOO_MANY_REQUESTS)

    # Always the same answer, whether or not the number is already registered:
    # a different one would turn this endpoint into a directory of citizens.
    return Response(status=status.HTTP_202_ACCEPTED)


@extend_schema(
    request=OtpVerifySerializer,
    responses={200: TokenPairSerializer, 400: ErrorSerializer},
    summary="Vérifier le code et ouvrir une session",
    tags=["authentification"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
def otp_verify(request: Request) -> Response:
    payload = OtpVerifySerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    data = payload.validated_data

    try:
        citizen = verify_otp(data["phone"], data["code"], accepted_terms=data["accepted_terms"])
    except ConsentRequired as error:
        return _error(request, "consent_required", str(error), status.HTTP_400_BAD_REQUEST)
    except OtpExpired as error:
        return _error(request, "otp_expired", str(error), status.HTTP_400_BAD_REQUEST)
    except InvalidCode as error:
        return _error(request, "invalid_code", str(error), status.HTTP_400_BAD_REQUEST)

    tokens = issue_tokens(citizen)
    return Response(
        TokenPairSerializer(
            {
                "access": tokens.access,
                "refresh": tokens.refresh,
                "access_expires_in": tokens.access_expires_in,
                "citizen": citizen,
            }
        ).data
    )


@extend_schema(
    request=RefreshSerializer,
    responses={200: TokenPairSerializer, 401: ErrorSerializer},
    summary="Renouveler la session",
    tags=["authentification"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
def refresh(request: Request) -> Response:
    payload = RefreshSerializer(data=request.data)
    payload.is_valid(raise_exception=True)

    try:
        tokens = rotate_refresh_token(payload.validated_data["refresh"])
    except InvalidToken as error:
        return _error(request, "invalid_token", str(error), status.HTTP_401_UNAUTHORIZED)

    return Response(
        TokenPairSerializer(
            {
                "access": tokens.access,
                "refresh": tokens.refresh,
                "access_expires_in": tokens.access_expires_in,
                "citizen": tokens.citizen,
            }
        ).data
    )


@extend_schema(
    request=RefreshSerializer,
    responses={204: None},
    summary="Fermer la session",
    tags=["authentification"],
)
@api_view(["POST"])
@citizen_auth
@permission_classes([IsAuthenticated])
def logout(request: Request) -> Response:
    revoke_all(citizen_of(request))
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    responses={200: CitizenSerializer},
    summary="Profil du citoyen connecté",
    tags=["compte"],
)
@api_view(["GET"])
@citizen_auth
@permission_classes([IsAuthenticated])
def me(request: Request) -> Response:
    return Response(CitizenSerializer(citizen_of(request)).data)


@extend_schema(
    responses={200: EntitlementListSerializer},
    summary="Droits d'accès du citoyen connecté",
    tags=["compte"],
)
@api_view(["GET"])
@citizen_auth
@permission_classes([IsAuthenticated])
def my_entitlements(request: Request) -> Response:
    entitlements = (
        citizen_of(request)
        .entitlements.select_related("zone", "plan_version__plan")
        .order_by("-created_at")[:50]
    )
    return Response(EntitlementListSerializer({"entitlements": entitlements}).data)


@extend_schema(
    responses={200: AccountExportSerializer},
    summary="Exporter les données du compte",
    tags=["compte"],
)
@api_view(["GET"])
@citizen_auth
@permission_classes([IsAuthenticated])
def me_export(request: Request) -> Response:
    payload = export_account(citizen_of(request))
    response = Response(AccountExportSerializer(payload).data)
    response["Content-Disposition"] = 'attachment; filename="dakar-wifi-export.json"'
    return response


@extend_schema(
    request=None,
    responses={204: None},
    summary="Supprimer le compte (anonymisation)",
    tags=["compte"],
)
@api_view(["POST"])
@citizen_auth
@permission_classes([IsAuthenticated])
def me_deletion(request: Request) -> Response:
    delete_account(citizen_of(request))
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    responses={200: SessionListSerializer},
    summary="Sessions réseau du citoyen connecté",
    tags=["compte"],
)
@api_view(["GET"])
@citizen_auth
@permission_classes([IsAuthenticated])
def my_sessions(request: Request) -> Response:
    sessions = (
        citizen_of(request)
        .network_sessions.select_related("hotspot__zone__site")
        .order_by("-start_at")[:50]
    )
    return Response(SessionListSerializer({"sessions": sessions}).data)


@extend_schema(
    request=None,
    responses={204: None, 404: ErrorSerializer, 503: ErrorSerializer},
    summary="Forcer la déconnexion d'une session",
    tags=["compte"],
)
@api_view(["POST"])
@citizen_auth
@permission_classes([IsAuthenticated])
def disconnect_my_session(request: Request, session_id) -> Response:
    session = NetworkSession.objects.filter(pk=session_id).first()
    if session is None:
        return _error(
            request,
            "session_not_found",
            "Cette session n'existe pas.",
            status.HTTP_404_NOT_FOUND,
        )
    try:
        disconnect_session(session, citizen=citizen_of(request))
    except SessionNotFound:
        return _error(
            request,
            "session_not_found",
            "Cette session n'existe pas.",
            status.HTTP_404_NOT_FOUND,
        )
    except SessionDisconnectFailed as error:
        http_status = (
            status.HTTP_503_SERVICE_UNAVAILABLE if error.retryable else status.HTTP_400_BAD_REQUEST
        )
        return _error(request, "disconnect_failed", str(error), http_status)
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    responses={200: TermsListSerializer},
    summary="Conditions à accepter",
    tags=["portail"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def terms(request: Request) -> Response:
    return Response(TermsListSerializer({"terms": current_terms_versions()}).data)
