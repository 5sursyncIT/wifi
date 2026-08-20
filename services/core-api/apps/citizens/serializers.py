import re

from rest_framework import serializers

# Normalised international format only (§8.1). Kept strict: a number the platform
# cannot dial is a wasted SMS and a support call.
E164 = re.compile(r"^\+[1-9]\d{7,14}$")


class OtpRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)

    def validate_phone(self, value):
        value = value.strip().replace(" ", "")
        if not E164.match(value):
            raise serializers.ValidationError(
                "Numéro attendu au format international, par exemple +221771234567."
            )
        return value


class OtpVerifySerializer(OtpRequestSerializer):
    code = serializers.CharField(max_length=10)
    accepted_terms = serializers.ListField(child=serializers.UUIDField(), allow_empty=True)


class RefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class CitizenSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    phone_e164 = serializers.CharField()
    email = serializers.CharField()
    preferred_language = serializers.CharField()
    status = serializers.CharField()
    verified_at = serializers.DateTimeField(allow_null=True)


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    access_expires_in = serializers.IntegerField()
    citizen = CitizenSerializer()


class TermsVersionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    type = serializers.CharField()
    version = serializers.CharField()
    content_url = serializers.CharField()
    summary = serializers.CharField()


class TermsListSerializer(serializers.Serializer):
    terms = TermsVersionSerializer(many=True)


class EntitlementSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    # DRF's metaclass pops declared fields off the class, so this does not actually
    # shadow Field.source; mypy cannot see that.
    source = serializers.CharField()  # type: ignore[assignment]
    status = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField(allow_null=True)
    zone = serializers.SerializerMethodField()
    plan = serializers.SerializerMethodField()

    def get_zone(self, entitlement) -> str:
        return entitlement.zone.code

    def get_plan(self, entitlement) -> str:
        return entitlement.plan_version.plan.code


class EntitlementListSerializer(serializers.Serializer):
    entitlements = EntitlementSerializer(many=True)


class SessionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    started_at = serializers.DateTimeField(source="start_at")
    ended_at = serializers.DateTimeField(source="stop_at", allow_null=True)
    bytes_in = serializers.IntegerField()
    bytes_out = serializers.IntegerField()
    site = serializers.SerializerMethodField()

    def get_site(self, session) -> str:
        if session.hotspot_id is None:
            return ""
        return session.hotspot.zone.site.name


class SessionListSerializer(serializers.Serializer):
    sessions = SessionSerializer(many=True)


class ConsentExportSerializer(serializers.Serializer):
    type = serializers.CharField()
    version = serializers.CharField()
    accepted_at = serializers.DateTimeField()
    source = serializers.CharField()  # type: ignore[assignment]


class DeviceExportSerializer(serializers.Serializer):
    mac_hash = serializers.CharField()
    label = serializers.CharField()  # type: ignore[assignment]
    first_seen_at = serializers.DateTimeField()
    last_seen_at = serializers.DateTimeField()


class EntitlementExportSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    source = serializers.CharField()  # type: ignore[assignment]
    status = serializers.CharField()
    zone = serializers.CharField()
    plan = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField(allow_null=True)


class OrderExportSerializer(serializers.Serializer):
    order_number = serializers.CharField()
    amount_xof = serializers.IntegerField()
    currency = serializers.CharField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()
    paid_at = serializers.DateTimeField(allow_null=True)


class TicketExportSerializer(serializers.Serializer):
    ticket_number = serializers.CharField()
    category = serializers.CharField()
    status = serializers.CharField()
    opened_at = serializers.DateTimeField()


class AccountCitizenSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    phone_e164 = serializers.CharField()
    email = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    preferred_language = serializers.CharField()
    status = serializers.CharField()
    verified_at = serializers.DateTimeField(allow_null=True)


class AccountExportSerializer(serializers.Serializer):
    exported_at = serializers.DateTimeField()
    citizen = AccountCitizenSerializer()
    consents = ConsentExportSerializer(many=True)
    devices = DeviceExportSerializer(many=True)
    entitlements = EntitlementExportSerializer(many=True)
    orders = OrderExportSerializer(many=True)
    tickets = TicketExportSerializer(many=True)
