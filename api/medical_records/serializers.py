from rest_framework import serializers

from api.accounts.models import PatientProfile

from api.consultations.models import Consultation

from .models import Diagnosis, PatientMedicalRecord


class PatientMedicalRecordSerializer(serializers.ModelSerializer):
    patient_uuid = serializers.UUIDField(source="patient.uuid", read_only=True)
    patient_name = serializers.CharField(source="patient.user.full_name", read_only=True)

    class Meta:
        model = PatientMedicalRecord
        fields = [
            "uuid",
            "patient_uuid",
            "patient_name",
            "blood_group",
            "allergies",
            "chronic_conditions",
            "weight",
            "height",
            "bmi",
            "created_at",
            "updated_at",
        ]


class PatientMedicalRecordWriteSerializer(serializers.ModelSerializer):
    patient_uuid = serializers.SlugRelatedField(
        source="patient",
        slug_field="uuid",
        queryset=PatientProfile.objects.select_related("user").all(),
    )

    class Meta:
        model = PatientMedicalRecord
        fields = [
            "patient_uuid",
            "blood_group",
            "allergies",
            "chronic_conditions",
            "weight",
            "height",
            "bmi",
        ]


class DiagnosisSerializer(serializers.ModelSerializer):
    consultation_uuid = serializers.UUIDField(source="consultation.uuid", read_only=True)
    consultation_appointment_uuid = serializers.UUIDField(
        source="consultation.appointment.uuid",
        read_only=True,
    )

    class Meta:
        model = Diagnosis
        fields = [
            "uuid",
            "consultation_uuid",
            "consultation_appointment_uuid",
            "disease_name",
            "icd10_code",
            "description",
            "type",
            "diagnosed_at",
            "created_at",
            "updated_at",
        ]


class DiagnosisWriteSerializer(serializers.ModelSerializer):
    consultation_uuid = serializers.SlugRelatedField(
        source="consultation",
        slug_field="uuid",
        queryset=Consultation.objects.select_related("appointment").all(),
    )

    class Meta:
        model = Diagnosis
        fields = [
            "consultation_uuid",
            "disease_name",
            "icd10_code",
            "description",
            "type",
        ]
