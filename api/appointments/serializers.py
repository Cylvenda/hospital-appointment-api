from rest_framework import serializers
from api.appointments.models import (
    IllnessCategory,
    Appointment,
    AppointmentLog,
    Payment,
)


class IllnessCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = IllnessCategory
        fields = ["uuid", "name", "description"]


class AppointmentSerializer(serializers.ModelSerializer):
    patient = serializers.StringRelatedField()
    doctor = serializers.StringRelatedField()
    illness_category = serializers.StringRelatedField(
        source="category.name", read_only=True
    )
    illness_category_uuid = serializers.UUIDField(
        source="category.uuid", read_only=True
    )

    class Meta:
        model = Appointment
        fields = [
            "uuid",
            "patient",
            "doctor",
            "illness_category",
            "illness_category_uuid",
            "description",
            "appointment_date",
            "status",
            "created_at",
        ]


class AppointmentCreateSerializer(serializers.ModelSerializer):
    illness_category_uuid = serializers.SlugRelatedField(
        source="category", slug_field="uuid", queryset=IllnessCategory.objects.all()
    )

    class Meta:
        model = Appointment
        fields = ["illness_category_uuid", "description", "appointment_date"]

    def create(self, validated_data):
        user = self.context["request"].user

        return Appointment.objects.create(
            created_by=user, status="pending", **validated_data
        )


class AppointmentAssignSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = ["doctor", "appointment_date", "status"]

    def validate(self, attrs):
        if attrs.get("status") not in ["approved", "rejected"]:
            raise serializers.ValidationError("Invalid status")
        return attrs


class AppointmentDoctorUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = ["diagnosis", "notes", "status"]

    def validate_status(self, value):
        if value != "completed":
            raise serializers.ValidationError("Doctor can only mark as completed")
        return value


class AppointmentLogSerializer(serializers.ModelSerializer):
    performed_by = serializers.StringRelatedField()

    class Meta:
        model = AppointmentLog
        fields = [
            "id",
            "appointment",
            "action",
            "performed_by",
            "timestamp",
        ]


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "uuid",
            "appointment",
            "amount",
            "status",
            "payment_method",
            "transaction_reference",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "uuid",
            "created_at",
            "updated_at",
            "status",
            "transaction_reference",
        ]
