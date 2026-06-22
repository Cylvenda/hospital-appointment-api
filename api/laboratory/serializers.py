from rest_framework import serializers

from api.accounts.models import DoctorProfile, PatientProfile
from api.consultations.models import Consultation

from .models import LabRequest, LabRequestItem, LabResult, LabTestType


class LabTestTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabTestType
        fields = [
            "uuid",
            "name",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["uuid", "created_at", "updated_at"]


class LabRequestItemSerializer(serializers.ModelSerializer):
    test_type_uuid = serializers.UUIDField(source="test_type.uuid", read_only=True)
    test_type_name = serializers.CharField(source="test_type.name", read_only=True)

    class Meta:
        model = LabRequestItem
        fields = [
            "uuid",
            "test_type_uuid",
            "test_type_name",
            "created_at",
            "updated_at",
        ]


class LabRequestSerializer(serializers.ModelSerializer):
    consultation_uuid = serializers.UUIDField(source="consultation.uuid", read_only=True)
    doctor_uuid = serializers.UUIDField(source="doctor.uuid", read_only=True)
    doctor_name = serializers.CharField(source="doctor.user.full_name", read_only=True)
    patient_uuid = serializers.UUIDField(source="patient.uuid", read_only=True)
    patient_name = serializers.CharField(source="patient.user.full_name", read_only=True)
    items = LabRequestItemSerializer(many=True, read_only=True)

    class Meta:
        model = LabRequest
        fields = [
            "uuid",
            "consultation_uuid",
            "doctor_uuid",
            "doctor_name",
            "patient_uuid",
            "patient_name",
            "status",
            "requested_at",
            "updated_at",
            "items",
        ]


class LabRequestWriteSerializer(serializers.ModelSerializer):
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
        model = LabRequest
        fields = [
            "consultation_uuid",
            "doctor_uuid",
            "patient_uuid",
            "status",
        ]


class LabRequestItemWriteSerializer(serializers.ModelSerializer):
    lab_request_uuid = serializers.SlugRelatedField(
        source="lab_request",
        slug_field="uuid",
        queryset=LabRequest.objects.all(),
    )
    test_type_uuid = serializers.SlugRelatedField(
        source="test_type",
        slug_field="uuid",
        queryset=LabTestType.objects.all(),
    )

    class Meta:
        model = LabRequestItem
        fields = [
            "lab_request_uuid",
            "test_type_uuid",
        ]


class LabResultSerializer(serializers.ModelSerializer):
    request_item_uuid = serializers.UUIDField(source="request_item.uuid", read_only=True)
    test_name = serializers.CharField(source="request_item.test_type.name", read_only=True)
    verified_by_uuid = serializers.UUIDField(source="verified_by.uuid", read_only=True)
    verified_by_name = serializers.CharField(source="verified_by.full_name", read_only=True)

    class Meta:
        model = LabResult
        fields = [
            "uuid",
            "request_item_uuid",
            "test_name",
            "result",
            "remarks",
            "verified_by_uuid",
            "verified_by_name",
            "verified_at",
            "created_at",
            "updated_at",
        ]


class LabResultWriteSerializer(serializers.ModelSerializer):
    request_item_uuid = serializers.SlugRelatedField(
        source="request_item",
        slug_field="uuid",
        queryset=LabRequestItem.objects.select_related("test_type", "lab_request").all(),
    )

    class Meta:
        model = LabResult
        fields = [
            "request_item_uuid",
            "result",
            "remarks",
            "verified_at",
        ]
