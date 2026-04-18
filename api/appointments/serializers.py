from rest_framework import serializers
from api.accounts.models import DoctorProfile
from api.accounts.models import SystemSettings
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
    patient_name = serializers.CharField(source="created_by.full_name", read_only=True)
    patient_email = serializers.EmailField(source="created_by.email", read_only=True)
    doctor_name = serializers.SerializerMethodField()
    doctor_uuid = serializers.UUIDField(source="doctor.uuid", read_only=True)
    payment_status = serializers.CharField(source="payment.status", read_only=True)
    illness_category = serializers.CharField(source="category.name", read_only=True)
    illness_category_uuid = serializers.UUIDField(
        source="category.uuid", read_only=True
    )

    def get_doctor_name(self, obj):
        if not obj.doctor:
            return None
        return obj.doctor.user.full_name or str(obj.doctor)

    class Meta:
        model = Appointment
        fields = [
            "uuid",
            "patient_name",
            "patient_email",
            "doctor_name",
            "doctor_uuid",
            "payment_status",
            "fee",
            "illness_category",
            "illness_category_uuid",
            "description",
            "preferred_date",
            "appointment_date",
            "start_time",
            "end_time",
            "status",
            "created_at",
        ]


class AppointmentCreateSerializer(serializers.ModelSerializer):
    illness_category_uuid = serializers.SlugRelatedField(
        source="category", slug_field="uuid", queryset=IllnessCategory.objects.all()
    )

    class Meta:
        model = Appointment
        fields = ["illness_category_uuid", "description", "preferred_date"]

    def create(self, validated_data):
        user = self.context["request"].user
        clinic_settings = SystemSettings.get_solo()

        return Appointment.objects.create(
            created_by=user,
            status="pending",
            fee=clinic_settings.appointment_fee,
            **validated_data
        )


class AppointmentAssignSerializer(serializers.ModelSerializer):
    doctor_uuid = serializers.SlugRelatedField(
        source="doctor",
        slug_field="uuid",
        queryset=DoctorProfile.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Appointment
        fields = [
            "doctor_uuid",
            "appointment_date",
            "start_time",
            "end_time",
            "status",
        ]

    def validate(self, attrs):
        status = attrs.get("status")
        if status and status not in [
            Appointment.Status.PENDING,
            Appointment.Status.ACCEPTED,
            Appointment.Status.CANCELLED,
            Appointment.Status.DECLINED,
        ]:
            raise serializers.ValidationError("Invalid status")
        return attrs


class AppointmentDoctorUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = ["diagnosis", "notes", "status"]

    def validate_status(self, value):
        if value not in [
            Appointment.Status.ACCEPTED,
            Appointment.Status.DECLINED,
            Appointment.Status.COMPLETED,
        ]:
            raise serializers.ValidationError(
                "Doctor can only mark appointments as accepted, declined, or completed"
            )
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


class DoctorOptionSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = DoctorProfile
        fields = ["uuid", "name", "is_available"]
