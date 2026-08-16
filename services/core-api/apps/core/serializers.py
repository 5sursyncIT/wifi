from rest_framework import serializers


class HealthChecksSerializer(serializers.Serializer):
    database = serializers.CharField(help_text="'ok' or 'error'")
    cache = serializers.CharField(help_text="'ok' or 'error'")


class HealthSerializer(serializers.Serializer):
    status = serializers.CharField(help_text="'ok' or 'unavailable'")
    environment = serializers.CharField(help_text="local, test, staging or production")
    version = serializers.CharField()
    checks = HealthChecksSerializer()
