"""Billing API serializers."""

from rest_framework import serializers

from apps.billing.models import Order


class OrderRequestSerializer(serializers.Serializer):
    nas_id = serializers.CharField(max_length=120)
    plan_version_id = serializers.UUIDField()


class OrderSerializer(serializers.ModelSerializer):
    mode = serializers.CharField(read_only=True, default="")
    instructions = serializers.CharField(read_only=True, default="")
    redirect_url = serializers.CharField(read_only=True, default="")
    entitlement_status = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "amount_xof",
            "currency",
            "status",
            "expires_at",
            "paid_at",
            "mode",
            "instructions",
            "redirect_url",
            "entitlement_status",
        ]

    def get_entitlement_status(self, order) -> str:
        entitlement = getattr(order, "entitlement", None)
        return entitlement.status if entitlement is not None else ""


class ReceiptSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan_version.plan.name", read_only=True)

    class Meta:
        model = Order
        fields = ["order_number", "plan_name", "amount_xof", "currency", "paid_at"]
