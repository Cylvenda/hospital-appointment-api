import os
import re
import logging
import hmac
import hashlib
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated

from api.appointments.models import Payment, Appointment
from api.payments.serializers import PaymentCreateInputSerializer, PaymentStatusSerializer
from api.payments.models import WebhookAuditLog
from api.payments.business import confirm_payment, fail_payment, PaymentAlreadyProcessed
from api.appointments.logs import create_log
from api.appointments.services import initiate_payment
from api.appointments.payments import PaymentGatewayError
from api.notifications.services import create_and_send_notification
from api.notifications.task import send_notification_email

logger = logging.getLogger(__name__)


def _email_superusers_about_gateway_failure(*, appointment, patient, error):
    """Alert active superusers without exposing gateway details to the patient."""
    recipients = (
        get_user_model()
        .objects.filter(is_superuser=True, is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )
    appointment_ref = appointment.appointment_id or str(appointment.uuid)
    patient_ref = patient.email or patient.phone or str(patient.pk)
    occurred_at = timezone.now().strftime("%Y-%m-%d %H:%M:%S %Z")

    for recipient_email in recipients:
        try:
            send_notification_email(
                subject=f"Payment gateway unavailable - Appointment {appointment_ref}",
                message=(
                    "A patient could not initiate an appointment payment because "
                    "the payment gateway was unavailable."
                ),
                recipient_email=recipient_email,
                extra_info=(
                    f"Occurred at: {occurred_at}\n"
                    f"Patient: {patient_ref}\n"
                    f"Gateway error: {error}"
                ),
                appointment_details=[
                    {"label": "Appointment ID", "value": appointment_ref},
                    {"label": "Reference UUID", "value": str(appointment.uuid)},
                    {"label": "Payment Status", "value": appointment.payment.get_status_display()},
                ],
                cta_label="Open PAMS",
            )
        except Exception:
            logger.exception(
                "Could not email superuser %s about payment gateway failure",
                recipient_email,
            )


class PaymentCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = PaymentCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        appointment_uuid = serializer.validated_data["appointment_uuid"]
        phone = serializer.validated_data.get("phone", "")

        try:
            appointment = Appointment.objects.select_related("payment").get(
                uuid=appointment_uuid
            )
        except Appointment.DoesNotExist:
            return Response(
                {"detail": "Appointment not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.user != appointment.created_by:
            return Response(
                {"detail": "You can only pay for your own appointment"},
                status=status.HTTP_403_FORBIDDEN,
            )

        payment = appointment.payment
        if payment.status == Payment.Status.SUCCESS:
            return Response(
                {"detail": "Already paid"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_phone = phone or request.user.phone
        if not user_phone:
            return Response(
                {"detail": "Phone number is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            initiate_payment(payment, request.user, appointment, user_phone)
        except PaymentGatewayError as exc:
            logger.exception(
                "Payment gateway unavailable for appointment %s", appointment_uuid
            )
            _email_superusers_about_gateway_failure(
                appointment=appointment,
                patient=request.user,
                error=exc,
            )
            return Response(
                {
                    "code": "payment_temporarily_unavailable",
                    "detail": (
                        "Payment is temporarily unavailable. "
                        "Your appointment is still saved; please try again later."
                    ),
                    "retryable": True,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as exc:
            logger.exception(
                "Failed to initiate payment for appointment %s", appointment_uuid
            )
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        payment.refresh_from_db()

        create_log(
            appointment=appointment,
            user=request.user,
            action=f"Payment initiated (ref: {payment.transaction_reference or 'pending'})",
        )
        create_and_send_notification(
            user=request.user,
            title="Payment Initiated",
            message="Your payment request has been submitted successfully and is now being processed.",
            notification_type="general",
            appointment=appointment,
            triggered_by=request.user,
            extra_info="You will receive another email once the payment is confirmed or if it fails.",
        )

        return Response(
            {
                "payment_uuid": payment.uuid,
                "reference": payment.transaction_reference,
                "status": payment.status,
            },
            status=status.HTTP_200_OK,
        )


class PaymentStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, uuid):
        try:
            payment = Payment.objects.select_related("appointment").get(uuid=uuid)
        except Payment.DoesNotExist:
            return Response(
                {"detail": "Payment not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.user != payment.appointment.created_by and request.user.role not in {
            "admin",
            "receptionist",
        }:
            return Response(
                {"detail": "Not authorized"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = PaymentStatusSerializer(payment)
        return Response(serializer.data)


def _verify_clickpesa_signature(raw_body: bytes, received_sig: str | None) -> bool:
    if not received_sig:
        return True
    checksum_key = os.getenv("CLICKPESA_CHECKSUM_KEY", "")
    if not checksum_key:
        return True
    expected = hmac.new(
        checksum_key.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, received_sig)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([])
def payment_webhook(request):
    raw_body = request.body
    received_sig = request.headers.get("X-Checksum") or request.headers.get(
        "X-ClickPesa-Checksum"
    )
    if not _verify_clickpesa_signature(raw_body, received_sig):
        return Response(
            {"detail": "Invalid signature"},
            status=status.HTTP_403_FORBIDDEN,
        )

    data = request.data
    transactions = data if isinstance(data, list) else [data]
    processed = 0
    results = []
    ip_address = request.META.get("REMOTE_ADDR")
    headers = dict(request.headers)

    for tx in transactions:
        event = (tx.get("event") or tx.get("status") or "").upper()
        event_data = tx.get("data") if isinstance(tx.get("data"), dict) else tx
        order_ref = event_data.get("orderReference")
        result = "not_found"
        payment = None

        if order_ref:
            payment = Payment.objects.filter(transaction_reference=order_ref).first()
            if not payment:
                payment = Payment.objects.filter(uuid=order_ref).first()
            if not payment:
                match = re.search(
                    r"PAYMENT(?:ID)?FORID?(\d+)$", str(order_ref).upper()
                )
                if match:
                    appointment_id = int(match.group(1))
                    payment = Payment.objects.filter(
                        appointment_id=appointment_id
                    ).first()

        with transaction.atomic():
            if payment:
                payment = Payment.objects.select_for_update().get(pk=payment.pk)

                if event in {"PAYMENT RECEIVED", "COMPLETED", "SUCCESS"}:
                    try:
                        confirm_payment(payment, event_data)
                        result = "success"
                        processed += 1
                    except PaymentAlreadyProcessed as exc:
                        result = exc.result
                elif event in {"PAYMENT FAILED", "FAILED"}:
                    try:
                        fail_payment(payment, event_data)
                        result = "failed"
                        processed += 1
                    except PaymentAlreadyProcessed as exc:
                        result = exc.result

            WebhookAuditLog.objects.create(
                payment=payment,
                raw_payload=data,
                headers=headers,
                ip_address=ip_address,
                processing_result=result,
            )
        results.append({"order_ref": order_ref, "result": result})

    return Response(
        {"message": "Webhook processed", "processed": processed, "results": results}
    )
