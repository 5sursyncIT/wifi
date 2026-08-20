from rest_framework import serializers


class RedeemRequestSerializer(serializers.Serializer):
    nas_id = serializers.CharField(max_length=120)
    code = serializers.CharField(max_length=20)
