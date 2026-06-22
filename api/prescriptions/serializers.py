from rest_framework import serializers

from api.accounts.models import DoctorProfile, PatientProfile
from api.consultations.models import Consultation

from .models import Prescription, PrescriptionItem


class PrescriptionItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrescriptionItem
        fields = [
            "uuid",
            "medicine_name",
            "dosage",
            "frequency",
            "duration",
            "instructions",
            "created_at",
            "updated_at",
        ]


class PrescriptionSerializer(serializers.ModelSerializer):
    consultation_uuid = serializers.UUIDField(source="consultation.uuid", read_only=True)
    doctor_uuid = serializers.UUIDField(source="doctor.uuid", read_only=True)
    doctor_name = serializers.CharField(source="doctor.user.full_name", read_only=True)
    patient_uuid = serializers.UUIDField(source="patient.uuid", read_only=True)
    patient_name = serializers.CharField(source="patient.user.full_name", read_only=True)
    items = PrescriptionItemSerializer(many=True, read_only=True)

    class Meta:
        model = Prescription
        fields = [
            "uuid",
            "consultation_uuid",
            "doctor_uuid",
            "doctor_name",
            "patient_uuid",
            "patient_name",
            "notes",
            "items",
            "created_at",
            "updated_at",
        ]


class PrescriptionWriteSerializer(serializers.ModelSerializer):
    consultation_uuid = serializers.SlugRelatedField(
        source="consultation",
        slug_field="uuid",
        queryset=Consultation.objects.select_related("appointment").all(),
    )
    doctor_uuid = serializers.SlugRelatedField(
        source="doctor",
        slug_field="uuid",
        queryset=DoctorProfile.objects.select_related("user").all(),
        required=False,
        allow_null=True,
    )
    patient_uuid = serializers.SlugRelatedField(
        source="patient",
        slug_field="uuid",
        queryset=PatientProfile.objects.select_related("user").all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Prescription
        fields = [
            "consultation_uuid",
            "doctor_uuid",
            "patient_uuid",
            "notes",
        ]


class PrescriptionItemWriteSerializer(serializers.ModelSerializer):
    prescription_uuid = serializers.SlugRelatedField(
        source="prescription",
        slug_field="uuid",
        queryset=Prescription.objects.all(),
    )

    class Meta:
        model = PrescriptionItem
        fields = [
            "prescription_uuid",
            "medicine_name",
            "dosage",
            "frequency",
            "duration",
            "instructions",
        ]
