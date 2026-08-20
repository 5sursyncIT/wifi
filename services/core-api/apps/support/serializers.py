from rest_framework import serializers

from apps.support.models import SupportTicket


class TicketRequestSerializer(serializers.Serializer):
    nas_id = serializers.CharField(max_length=120, required=False, allow_blank=True)
    category = serializers.ChoiceField(choices=SupportTicket.Category.choices)
    message = serializers.CharField(min_length=10, max_length=2000)
    order_id = serializers.UUIDField(required=False)


class TicketSerializer(serializers.Serializer):
    ticket_number = serializers.CharField()
    category = serializers.CharField()
    status = serializers.CharField()
    opened_at = serializers.DateTimeField()
