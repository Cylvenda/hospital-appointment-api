from rest_framework import serializers
from api.appointments.models import Payment

class PaymentCreateInputSerializer(serializers.Serializer):
    appointment_uuid = serializers.UUIDField()
    phone = serializers.CharField(required=False, allow_blank=True)

class PaymentCreateOutputSerializer(serializers.Serializer):
    payment_uuid = serializers.UUIDField(source="uuid")
    reference = serializers.CharField()
    status = serializers.CharField()

class PaymentStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "uuid",
            "status",
            "paid_at",
            "gateway_transaction_id",
            "receipt_number",
            "raw_response",
            "payment_method",
            "transaction_reference",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
