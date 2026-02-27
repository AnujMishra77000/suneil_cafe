from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(source="order.id", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "order_id",
            "recipient_type",
            "recipient_identifier",
            "event_type",
            "title",
            "message",
            "payload",
            "status",
            "is_read",
            "created_at",
            "updated_at",
        ]


class NotificationRecipientSerializer(serializers.Serializer):
    recipient_type = serializers.ChoiceField(choices=Notification.RecipientType.choices)
    recipient_identifier = serializers.CharField(required=False, allow_blank=True, max_length=100)

    def validate_recipient_identifier(self, value):
        return (value or "").strip()


class NotificationFeedQuerySerializer(NotificationRecipientSerializer):
    limit = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)
    since_id = serializers.IntegerField(required=False, min_value=1)


class NotificationMarkReadSerializer(NotificationRecipientSerializer):
    notification_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )
