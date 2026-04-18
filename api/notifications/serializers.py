from rest_framework import serializers
from .models import Notification


class NotificationUserSerializer(serializers.Serializer):
    uuid = serializers.UUIDField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()


class NotificationSerializer(serializers.ModelSerializer):
    triggered_by = NotificationUserSerializer(read_only=True)

    class Meta:
        model = Notification
        fields = [
            "uuid",
            "title",
            "message",
            "notification_type",
            "is_read",
            "read_at",
            "appointment_uuid",
            "triggered_by",
            "created_at",
        ]


class EmptySerializer(serializers.Serializer):
    pass
