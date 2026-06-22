from rest_framework import serializers

from api.accounts.models import PatientProfile
from api.consultations.models import Consultation

from .models import Invoice, InvoiceItem


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = [
            "uuid",
            "item_type",
            "description",
            "quantity",
            "unit_price",
            "amount",
            "created_at",
            "updated_at",
        ]


class InvoiceSerializer(serializers.ModelSerializer):
    patient_uuid = serializers.UUIDField(source="patient.uuid", read_only=True)
    patient_name = serializers.CharField(source="patient.user.full_name", read_only=True)
    consultation_uuid = serializers.UUIDField(source="consultation.uuid", read_only=True)
    items = InvoiceItemSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "uuid",
            "invoice_number",
            "patient_uuid",
            "patient_name",
            "consultation_uuid",
            "total_amount",
            "status",
            "issued_at",
            "paid_at",
            "created_at",
            "updated_at",
            "items",
        ]


class InvoiceWriteSerializer(serializers.ModelSerializer):
    patient_uuid = serializers.SlugRelatedField(
        source="patient",
        slug_field="uuid",
        queryset=PatientProfile.objects.select_related("user").all(),
    )
    consultation_uuid = serializers.SlugRelatedField(
        source="consultation",
        slug_field="uuid",
        queryset=Consultation.objects.select_related("appointment").all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Invoice
        fields = [
            "patient_uuid",
            "consultation_uuid",
            "status",
        ]


class InvoiceItemWriteSerializer(serializers.ModelSerializer):
    invoice_uuid = serializers.SlugRelatedField(
        source="invoice",
        slug_field="uuid",
        queryset=Invoice.objects.all(),
    )

    class Meta:
        model = InvoiceItem
        fields = [
            "invoice_uuid",
            "item_type",
            "description",
            "quantity",
            "unit_price",
        ]

