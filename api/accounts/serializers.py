from djoser.serializers import UserSerializer
from django.contrib.auth import get_user_model
from rest_framework import serializers


class CustomUserSerializer(UserSerializer):
    is_admin = serializers.BooleanField(source="is_superuser", read_only=True)

    class Meta(UserSerializer.Meta):
        model = get_user_model()
        fields = (
            "uuid",
            "first_name",
            "last_name",
            "role",
            "email",
            "phone",
            "is_active",
            "is_staff",
            "is_admin",
        )
        read_only_fields = ("uuid",)
