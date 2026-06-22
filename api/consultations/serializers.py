from rest_framework import serializers

from api.appointments.models import Appointment
from api.accounts.models import DoctorProfile, PatientProfile
from api.billing.models import Invoice, InvoiceItem
from api.laboratory.models import LabRequest, LabRequestItem, LabTestType
from api.medical_records.models import Diagnosis
from api.prescriptions.models import Prescription, PrescriptionItem

from .models import Consultation


class ConsultationSerializer(serializers.ModelSerializer):
    appointment_uuid = serializers.UUIDField(source="appointment.uuid", read_only=True)
    doctor_uuid = serializers.UUIDField(source="doctor.uuid", read_only=True)
    doctor_name = serializers.CharField(source="doctor.user.full_name", read_only=True)
    patient_uuid = serializers.UUIDField(source="patient.uuid", read_only=True)
    patient_name = serializers.CharField(source="patient.user.full_name", read_only=True)

    class Meta:
        model = Consultation
        fields = [
            "uuid",
            "appointment_uuid",
            "doctor_uuid",
            "doctor_name",
            "patient_uuid",
            "patient_name",
            "chief_complaint",
            "history_of_present_illness",
            "physical_examination",
            "provisional_diagnosis",
            "status",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]


class ConsultationWriteSerializer(serializers.ModelSerializer):
    appointment_uuid = serializers.SlugRelatedField(
        source="appointment",
        slug_field="uuid",
        queryset=Appointment.objects.all(),
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
        model = Consultation
        fields = [
            "appointment_uuid",
            "doctor_uuid",
            "patient_uuid",
            "chief_complaint",
            "history_of_present_illness",
            "physical_examination",
            "provisional_diagnosis",
            "status",
            "completed_at",
        ]

    def create(self, validated_data):
        appointment = validated_data.get("appointment")
        if appointment and not validated_data.get("doctor"):
            validated_data["doctor"] = getattr(appointment, "doctor", None)

        if appointment and not validated_data.get("patient"):
            created_by = getattr(appointment, "created_by", None)
            validated_data["patient"] = getattr(created_by, "patient_profile", None)

        consultation, _ = Consultation.objects.update_or_create(
            appointment=appointment,
            defaults=validated_data,
        )
        return consultation

    def to_representation(self, instance):
        return ConsultationSerializer(instance, context=self.context).data


class DiagnosisCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Diagnosis
        fields = ["disease_name", "icd10_code", "description", "type"]


class PrescriptionItemInputSerializer(serializers.Serializer):
    medicine_name = serializers.CharField(max_length=255)
    dosage = serializers.CharField(max_length=100)
    frequency = serializers.CharField(max_length=100)
    duration = serializers.CharField(max_length=100)
    instructions = serializers.CharField(required=False, allow_blank=True)


class PrescriptionCreateSerializer(serializers.ModelSerializer):
    items = PrescriptionItemInputSerializer(many=True, required=False, default=list)

    class Meta:
        model = Prescription
        fields = ["notes", "items"]


class LabRequestItemInputSerializer(serializers.Serializer):
    test_type_uuid = serializers.SlugRelatedField(
        source="test_type",
        slug_field="uuid",
        queryset=LabTestType.objects.all(),
    )


class LabRequestCreateSerializer(serializers.ModelSerializer):
    items = LabRequestItemInputSerializer(many=True, required=True)

    class Meta:
        model = LabRequest
        fields = ["status", "items"]


class InvoiceItemInputSerializer(serializers.Serializer):
    item_type = serializers.ChoiceField(choices=InvoiceItem.ItemType.choices)
    description = serializers.CharField(max_length=255)
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, default=1, required=False)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, default=0, required=False)


class InvoiceCreateSerializer(serializers.ModelSerializer):
    items = InvoiceItemInputSerializer(many=True, required=False, default=list)

    class Meta:
        model = Invoice
        fields = ["items", "status"]
