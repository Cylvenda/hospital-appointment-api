from django.db import transaction
from django.utils import timezone
from api.appointments.models import Payment, Appointment
from api.notifications.services import create_and_send_notification


class PaymentAlreadyProcessed(Exception):
    def __init__(self, result):
        self.result = result


def confirm_payment(payment: Payment, event_data: dict):
    with transaction.atomic():
        appointment = Appointment.objects.select_for_update().get(pk=payment.appointment.pk)
        payment.refresh_from_db()

        if payment.status == Payment.Status.SUCCESS:
            raise PaymentAlreadyProcessed("already_processed")

        payment.status = Payment.Status.SUCCESS
        payment.paid_at = timezone.now()
        payment.gateway_transaction_id = (
            event_data.get("transactionId") or event_data.get("transaction_id") or payment.transaction_reference
        )
        payment.payment_method = event_data.get("channel") or payment.payment_method
        payment.raw_response = event_data
        payment.receipt_number = (
            f"RCPT-{payment.uuid.hex[:8].upper()}-{timezone.now().strftime('%Y%m%d')}"
        )
        payment.save(
            update_fields=[
                "status",
                "paid_at",
                "gateway_transaction_id",
                "payment_method",
                "raw_response",
                "receipt_number",
                "updated_at",
            ]
        )

        if (
            appointment.doctor_id
            and appointment.appointment_date
            and appointment.start_time
            and appointment.status == Appointment.Status.PENDING
        ):
            appointment.status = Appointment.Status.CONFIRMED
            appointment.save(update_fields=["status", "updated_at"])

    def _notify():
        create_and_send_notification(
            user=appointment.created_by,
            title="Payment Received Successfully",
            message="Your appointment payment was received successfully.",
            notification_type="payment_success",
            appointment=appointment,
            triggered_by=appointment.created_by,
            extra_info="Your appointment can now proceed to the next review stage.",
        )

    transaction.on_commit(_notify)


def fail_payment(payment: Payment, event_data: dict):
    with transaction.atomic():
        appointment = Appointment.objects.select_for_update().get(pk=payment.appointment.pk)
        payment.refresh_from_db()

        if payment.status == Payment.Status.SUCCESS:
            raise PaymentAlreadyProcessed("already_confirmed")

        if payment.status == Payment.Status.FAILED:
            raise PaymentAlreadyProcessed("already_failed")

        payment.status = Payment.Status.FAILED
        payment.payment_method = event_data.get("channel") or payment.payment_method
        payment.raw_response = event_data
        payment.save(
            update_fields=[
                "status",
                "payment_method",
                "raw_response",
                "updated_at",
            ]
        )

        if appointment.status == Appointment.Status.PENDING:
            appointment.status = Appointment.Status.CANCELLED
            appointment.save(update_fields=["status", "updated_at"])

    def _notify():
        create_and_send_notification(
            user=appointment.created_by,
            title="Payment Failed",
            message="Your appointment payment failed. Please try again.",
            notification_type="general",
            appointment=appointment,
            triggered_by=appointment.created_by,
            extra_info="You can retry the payment from your appointment page.",
        )

    transaction.on_commit(_notify)
