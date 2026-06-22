from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Dispensing, DispensingItem, Medicine
from api.prescriptions.models import Prescription


class MedicineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Medicine
        fields = [
            "uuid",
            "name",
            "generic_name",
            "unit_price",
            "stock_quantity",
            "expiry_date",
            "created_at",
            "updated_at",
        ]


class DispensingItemSerializer(serializers.ModelSerializer):
    medicine_uuid = serializers.UUIDField(source="medicine.uuid", read_only=True)
    medicine_name = serializers.CharField(source="medicine.name", read_only=True)

    class Meta:
        model = DispensingItem
        fields = [
            "uuid",
            "medicine_uuid",
            "medicine_name",
            "quantity",
            "created_at",
            "updated_at",
        ]


class DispensingSerializer(serializers.ModelSerializer):
    prescription_uuid = serializers.UUIDField(source="prescription.uuid", read_only=True)
    patient_name = serializers.CharField(source="prescription.patient.user.full_name", read_only=True)
    pharmacist_name = serializers.CharField(source="pharmacist.full_name", read_only=True)
    pharmacist_uuid = serializers.UUIDField(source="pharmacist.uuid", read_only=True)
    items = DispensingItemSerializer(many=True, read_only=True)

    class Meta:
        model = Dispensing
        fields = [
            "uuid",
            "prescription_uuid",
            "patient_name",
            "pharmacist_uuid",
            "pharmacist_name",
            "status",
            "dispensed_at",
            "created_at",
            "updated_at",
            "items",
        ]


class DispensingWriteSerializer(serializers.ModelSerializer):
    prescription_uuid = serializers.SlugRelatedField(
        source="prescription",
        slug_field="uuid",
        queryset=Prescription.objects.select_related("patient__user", "doctor__user").all(),
    )
    pharmacist_uuid = serializers.SlugRelatedField(
        source="pharmacist",
        slug_field="uuid",
        queryset=get_user_model().objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Dispensing
        fields = [
            "uuid",
            "prescription_uuid",
            "pharmacist_uuid",
            "status",
            "dispensed_at",
        ]

    def validate(self, attrs):
        status = attrs.get("status", getattr(self.instance, "status", None))
        dispensed_at = attrs.get("dispensed_at", getattr(self.instance, "dispensed_at", None))

        if status == Dispensing.Status.DISPENSED and not dispensed_at:
            raise serializers.ValidationError(
                {"dispensed_at": "Dispensed date/time is required when marking a dispensing as dispensed."}
            )

        if status == Dispensing.Status.PENDING and dispensed_at:
            raise serializers.ValidationError(
                {"dispensed_at": "Pending dispensings should not have a dispensed timestamp."}
            )

        return attrs


class DispensingItemWriteSerializer(serializers.ModelSerializer):
    dispensing_uuid = serializers.SlugRelatedField(
        source="dispensing",
        slug_field="uuid",
        queryset=Dispensing.objects.all(),
    )
    medicine_uuid = serializers.SlugRelatedField(
        source="medicine",
        slug_field="uuid",
        queryset=Medicine.objects.all(),
    )

    class Meta:
        model = DispensingItem
        fields = [
            "uuid",
            "dispensing_uuid",
            "medicine_uuid",
            "quantity",
        ]

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value
