from rest_framework import viewsets
from rest_framework.decorators import action, api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.db.models import Q
import re
from api.accounts.models import DoctorProfile
from api.appointments.models import Appointment, IllnessCategory, Payment
from api.appointments.serializers import (
    AppointmentSerializer,
    AppointmentCreateSerializer,
    AppointmentAssignSerializer,
    AppointmentDoctorUpdateSerializer,
    DoctorOptionSerializer,
    IllnessCategorySerializer,
)
from api.notifications.services import create_and_send_notification
from .logs import create_log
from .services import initiate_payment
from api.notifications.task import send_notification_email


def _notify(
    *,
    user,
    title,
    message,
    notification_type,
    appointment=None,
    triggered_by=None,
    extra_info=None,
):
    if not user:
        return
    create_and_send_notification(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        appointment=appointment,
        triggered_by=triggered_by,
        extra_info=extra_info,
    )


class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.all().order_by("-created_at")
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def get_serializer_class(self):
        user = self.request.user
        role = user.role

        if self.action == "create":
            return AppointmentCreateSerializer

        if self.action in ["update", "partial_update"]:
            if role in ["receptionist", "admin"]:
                return AppointmentAssignSerializer
            if role == "doctor":
                return AppointmentDoctorUpdateSerializer

        return AppointmentSerializer

    def get_queryset(self):
        user = self.request.user
        role = user.role

        if role == "patient":
            return Appointment.objects.filter(created_by=user).order_by("-created_at")
        if role == "doctor":
            return Appointment.objects.filter(doctor__user=user).order_by("-created_at")
        if role == "receptionist":
            return Appointment.objects.all().order_by("-created_at")
        if role == "admin":
            return Appointment.objects.all().order_by("-created_at")

        return Appointment.objects.none()

    @action(detail=False, methods=["get"], url_path="doctors")
    def doctors(self, request):
        if request.user.role not in ["admin", "receptionist"]:
            raise PermissionDenied("You do not have permission to view doctors")

        queryset = (
            DoctorProfile.objects.select_related("user")
            .filter(is_available=True)
        )
        serializer = DoctorOptionSerializer(queryset, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        user = self.request.user
        appointment = serializer.save()
        Payment.objects.create(appointment=appointment, amount=appointment.fee)

        create_log(
            appointment=appointment,
            user=user,
            action="Appointment created (awaiting payment)",
        )
        send_notification_email(
            subject="Appointment Created",
            message="Your appointment request has been created successfully and is now waiting for payment confirmation.",
            recipient_email=user.email,
            appointment_details=appointment,
            action_details="Appointment created (awaiting payment)",
            notification_type="appointment_booked",
            triggered_by=user,
            extra_info="After payment is completed, the hospital team can continue processing your appointment request.",
        )

        doctor_user = getattr(appointment.doctor, "user", None)
        send_notification_email(
            subject="New Appointment Booked",
            message="A new appointment request has been booked and assigned to you For review.",
            recipient_email=doctor_user.email,
            appointment_details=appointment,
            action_details="New appointment assigned",
            notification_type="appointment_booked",
            triggered_by=user,
        )

    @action(detail=True, methods=["post"])
    def pay(self, request, uuid=None):
        appointment = self.get_object()
        user = request.user
        preffered_phone_number = request.data.get("phone")

        if user != appointment.created_by:
            raise PermissionDenied("You can only pay your own appointment")

        payment = appointment.payment
        if payment.status == Payment.Status.COMPLETED:
            return Response({"message": "Already paid"})

        response = initiate_payment(payment, user, appointment, preffered_phone_number)

        create_log(
            appointment=appointment,
            user=user,
            action=f"Payment initiated (ref: {payment.transaction_reference or 'pending'})",
        )
        _notify(
            user=user,
            title="Payment Initiated",
            message="Your payment request has been submitted successfully and is now being processed.",
            notification_type="general",
            appointment=appointment,
            triggered_by=user,
            extra_info="You will receive another email once the payment is confirmed or if it fails.",
        )

        return Response(
            {
                "message": "Payment initiated",
                "payment_uuid": payment.uuid,
                "gateway": response,
            }
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, uuid=None):
        appointment = self.get_object()
        user = request.user

        if user != appointment.created_by:
            raise PermissionDenied("You can only cancel your appointment")

        appointment.status = Appointment.Status.CANCELLED
        appointment.save(update_fields=["status", "updated_at"])

        create_log(appointment, user, "Appointment cancelled by patient")
        _notify(
            user=user,
            title="Appointment Cancelled",
            message="Your appointment has been cancelled successfully.",
            notification_type="appointment_cancelled",
            appointment=appointment,
            triggered_by=user,
            extra_info=appointment.cancel_reason or "If needed, you can create a new appointment request from your dashboard.",
        )

        doctor_user = getattr(appointment.doctor, "user", None)
        _notify(
            user=doctor_user,
            title="Appointment Cancelled",
            message="A patient cancelled an appointment that had been assigned to you.",
            notification_type="appointment_cancelled",
            appointment=appointment,
            triggered_by=user,
            extra_info=appointment.cancel_reason or None,
        )

        return Response({"message": "Appointment cancelled successfully"})

    def perform_update(self, serializer):
        old = self.get_object()
        user = self.request.user
        role = user.role
        old_status = old.status
        old_doctor_id = old.doctor_id
        old_appointment_date = old.appointment_date

        if role == "patient":
            if old.created_by != user:
                raise PermissionDenied("Not your appointment")
            # if old.payment.status == Appointment.Status.COMPLETED:
            #     raise PermissionDenied("Cannot update after appointment is being completed")

        if role == "doctor" and getattr(old.doctor, "user", None) != user:
            raise PermissionDenied("Not assigned to this appointment")

        if (
            role in ["receptionist", "admin"]
            and old.payment.status != Payment.Status.COMPLETED
        ):
            raise PermissionDenied("Cannot process unpaid appointment")

        updated = serializer.save()

        if role in ["receptionist", "admin"]:
            if old_status != updated.status:
                create_log(updated, user, f"Status -> {updated.status}")
                _notify(
                    user=updated.created_by,
                    title="Appointment Status Updated",
                    message=f"Your appointment status has been updated to '{updated.get_status_display()}'.",
                    notification_type=(
                        "appointment_approved"
                        if updated.status == Appointment.Status.ACCEPTED
                        else "appointment_rejected"
                    ),
                    appointment=updated,
                    triggered_by=user,
                )

            if old_doctor_id != updated.doctor_id and updated.doctor:
                create_log(updated, user, f"Doctor assigned -> {updated.doctor}")
                _notify(
                    user=updated.doctor.user,
                    title="New Appointment Assigned",
                    message="A new appointment has been assigned to you by the hospital team.",
                    notification_type="appointment_booked",
                    appointment=updated,
                    triggered_by=user,
                )

            if old_appointment_date != updated.appointment_date:
                create_log(updated, user, f"Scheduled -> {updated.appointment_date}")
                _notify(
                    user=updated.created_by,
                    title="Appointment Rescheduled",
                    message="Your appointment has been rescheduled. Please review the updated date and time below.",
                    notification_type="appointment_rescheduled",
                    appointment=updated,
                    triggered_by=user,
                    extra_info="Please make sure the new schedule still works for you.",
                )

        elif role == "doctor":
            if old.status != updated.status:
                if updated.status == Appointment.Status.ACCEPTED:
                    create_log(updated, user, "Appointment accepted by doctor")
                    _notify(
                        user=updated.created_by,
                        title="Appointment Accepted",
                        message="Your doctor has accepted your appointment.",
                        notification_type="appointment_approved",
                        appointment=updated,
                        triggered_by=user,
                    )
                elif updated.status == Appointment.Status.DECLINED:
                    create_log(updated, user, "Appointment declined by doctor")
                    _notify(
                        user=updated.created_by,
                        title="Appointment Declined",
                        message="Your doctor declined your appointment. Please review the appointment details and book another slot if needed.",
                        notification_type="appointment_rejected",
                        appointment=updated,
                        triggered_by=user,
                    )
                elif updated.status == Appointment.Status.COMPLETED:
                    create_log(updated, user, "Appointment completed")
                    _notify(
                        user=updated.created_by,
                        title="Appointment Completed",
                        message="Your doctor marked your appointment as completed.",
                        notification_type="general",
                        appointment=updated,
                        triggered_by=user,
                        extra_info="Thank you for using the appointment system.",
                    )


class IllnessCategoryViewSet(viewsets.ModelViewSet):
    queryset = IllnessCategory.objects.all()
    serializer_class = IllnessCategorySerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def perform_create(self, serializer):
        user = self.request.user
        if user.role not in ["admin", "receptionist"]:
            raise PermissionDenied("You do not have permission to create categories")
        serializer.save()

    def perform_update(self, serializer):
        user = self.request.user
        if user.role not in ["admin", "receptionist"]:
            raise PermissionDenied("You do not have permission to update categories")
        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        if user.role not in ["admin", "receptionist"]:
            raise PermissionDenied("You do not have permission to delete categories")
        instance.delete()


@api_view(["POST"])
def clickpesa_webhook(request):
    data = request.data
    transactions = data if isinstance(data, list) else [data]
    processed = 0

    for tx in transactions:
        event = (tx.get("event") or tx.get("status") or "").upper()
        event_data = tx.get("data") if isinstance(tx.get("data"), dict) else tx

        order_ref = event_data.get("orderReference")
        if not order_ref:
            continue

        payment = Payment.objects.filter(transaction_reference=order_ref).first()
        if not payment:
            payment = Payment.objects.filter(uuid=order_ref).first()
        if not payment:
            # Backward-compat support for legacy refs like PAYMENTIDFOR1 / PAYMENTFORID1
            match = re.search(r"PAYMENT(?:ID)?FORID?(\d+)$", str(order_ref).upper())
            if match:
                appointment_id = int(match.group(1))
                payment = Payment.objects.filter(appointment_id=appointment_id).first()
        if not payment:
            continue

        appointment = payment.appointment
        gateway_message = event_data.get("message")

        if event in {"PAYMENT RECEIVED", "COMPLETED", "SUCCESS"}:
            if payment.status != Payment.Status.COMPLETED:
                payment.status = Payment.Status.COMPLETED
                payment.payment_method = (
                    event_data.get("channel") or payment.payment_method
                )
                payment.save(update_fields=["status", "payment_method", "updated_at"])
                create_log(appointment, None, f"Payment completed ({order_ref})")
                _notify(
                    user=appointment.created_by,
                    title="Payment Successful",
                    message="Your appointment payment was received successfully.",
                    notification_type="payment_success",
                    appointment=appointment,
                    triggered_by=appointment.created_by,
                    extra_info="Your appointment can now proceed to the next review stage.",
                )
                processed += 1
        elif event in {"PAYMENT FAILED", "FAILED"}:
            if payment.status != Payment.Status.FAILED:
                payment.status = Payment.Status.FAILED
                payment.payment_method = (
                    event_data.get("channel") or payment.payment_method
                )
                payment.save(update_fields=["status", "payment_method", "updated_at"])
                detail = f": {gateway_message}" if gateway_message else ""
                create_log(appointment, None, f"Payment failed ({order_ref}){detail}")
                _notify(
                    user=appointment.created_by,
                    title="Payment Failed",
                    message=(
                        gateway_message
                        or "Your appointment payment failed. Please try again."
                    ),
                    notification_type="general",
                    appointment=appointment,
                    triggered_by=appointment.created_by,
                    extra_info="You can retry the payment from your appointment page.",
                )
                processed += 1

    return Response({"message": "Webhook processed", "processed": processed})
