from django.contrib.auth import get_user_model
from openwisp_users.api.authentication import BearerAuthentication
from rest_framework import serializers, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import GroupNotFound, assign_group, disconnect_user

User = get_user_model()


class AssignGroupSerializer(serializers.Serializer):
    username = serializers.CharField()
    group_name = serializers.CharField()


class DisconnectSerializer(serializers.Serializer):
    username = serializers.CharField()


class _BaseView(APIView):
    # Same authentication as the upstream OpenWISP REST API, so a single service
    # token works across both.
    authentication_classes = [BearerAuthentication, SessionAuthentication]
    # PROOF OF CONCEPT: staff-only. Before production this must be narrowed to the
    # caller's own organizations — see infra/openwisp-extension/README.md.
    permission_classes = [IsAdminUser]

    def get_user(self, username):
        return User.objects.filter(username=username).first()


class AssignGroupView(_BaseView):
    """Move a user to a RADIUS group, which triggers a CoA on open sessions."""

    def post(self, request):
        payload = AssignGroupSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        user = self.get_user(data["username"])
        if user is None:
            return Response({"detail": "Unknown user."}, status=status.HTTP_404_NOT_FOUND)

        try:
            user_group, changed = assign_group(user, data["group_name"])
        except GroupNotFound as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "username": user.username,
                "group_name": user_group.group.name,
                "organization": str(user_group.group.organization_id),
                "changed": changed,
            }
        )


class DisconnectView(_BaseView):
    """Send a RADIUS Disconnect-Request for every open session of a user."""

    def post(self, request):
        payload = DisconnectSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        user = self.get_user(payload.validated_data["username"])
        if user is None:
            return Response({"detail": "Unknown user."}, status=status.HTTP_404_NOT_FOUND)

        results = disconnect_user(user)
        return Response({"username": user.username, "sessions": results})
