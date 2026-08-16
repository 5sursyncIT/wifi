from django.conf import settings
from rest_framework import serializers


class PlanOfferSerializer(serializers.Serializer):
    """Public view of an offer.

    Deliberately omits `radius_profile_ref`: RADIUS references belong to the network
    layer and must never appear in a payload served to a browser (§8.9).
    """

    code = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    type = serializers.CharField()
    price_xof = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    connection_seconds = serializers.SerializerMethodField()
    validity_seconds = serializers.SerializerMethodField()
    quota_total_bytes = serializers.SerializerMethodField()
    bandwidth_down_kbps = serializers.SerializerMethodField()
    bandwidth_up_kbps = serializers.SerializerMethodField()
    max_simultaneous_sessions = serializers.SerializerMethodField()

    def get_price_xof(self, plan) -> int:
        return plan.current_version.price_xof

    def get_currency(self, plan) -> str:
        return settings.DEFAULT_CURRENCY

    def get_connection_seconds(self, plan) -> int | None:
        return plan.current_version.connection_seconds

    def get_validity_seconds(self, plan) -> int | None:
        return plan.current_version.validity_seconds

    def get_quota_total_bytes(self, plan) -> int | None:
        return plan.current_version.quota_total_bytes

    def get_bandwidth_down_kbps(self, plan) -> int | None:
        return plan.current_version.bandwidth_down_kbps

    def get_bandwidth_up_kbps(self, plan) -> int | None:
        return plan.current_version.bandwidth_up_kbps

    def get_max_simultaneous_sessions(self, plan) -> int:
        return plan.current_version.max_simultaneous_sessions


class ZoneSerializer(serializers.Serializer):
    code = serializers.CharField()
    # DRF's metaclass pops declared fields off the class, so this does not actually
    # shadow Field.label; mypy cannot see that.
    label = serializers.CharField()  # type: ignore[assignment]
    access_mode = serializers.CharField()
    timezone = serializers.CharField()
    welcome_message = serializers.CharField()


class SiteSerializer(serializers.Serializer):
    name = serializers.CharField()
    address = serializers.CharField()
    organization = serializers.SerializerMethodField()

    def get_organization(self, site) -> str:
        return site.organization.name


class FallbackSerializer(serializers.Serializer):
    active = serializers.BooleanField()
    reason = serializers.CharField(allow_blank=True)


class PortalContextSerializer(serializers.Serializer):
    zone = ZoneSerializer()
    site = SiteSerializer()
    fallback = FallbackSerializer()
    plans = PlanOfferSerializer(many=True)
    redirect_url = serializers.CharField(allow_null=True)


class PortalPlansSerializer(serializers.Serializer):
    plans = PlanOfferSerializer(many=True)


class PublicSiteSerializer(serializers.Serializer):
    """Map entry. Carries nothing that identifies equipment (§8.9)."""

    name = serializers.CharField()
    address = serializers.CharField()
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    status = serializers.CharField()
    hotspot_count = serializers.IntegerField()
    access_modes = serializers.ListField(child=serializers.CharField())


class PublicSitesSerializer(serializers.Serializer):
    sites = PublicSiteSerializer(many=True)


class ErrorSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    request_id = serializers.CharField()
