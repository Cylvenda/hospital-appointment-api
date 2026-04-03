from rest_framework import viewsets
from rest_framework.decorators import action, api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view
import re
from api.appointments.models import Appointment, IllnessCategory, Payment
from api.appointments.serializers import (
    AppointmentSerializer,
    AppointmentCreateSerializer,
    AppointmentAssignSerializer,
    AppointmentDoctorUpdateSerializer,
    IllnessCategorySerializer,
)
from api.notifications.services import create_and_send_notification
from .logs import create_log
from .services import initiate_payment


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


@extend_schema_view(
    list=extend_schema(tags=["Appointments"]),
    retrieve=extend_schema(tags=["Appointments"]),
    create=extend_schema(tags=["Appointments"]),
    update=extend_schema(tags=["Appointments"]),
    partial_update=extend_schema(tags=["Appointments"]),
    destroy=extend_schema(tags=["Appointments"]),
)
class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.all()
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def get_serializer_class(self):
        user = self.request.user
        role = user.role

        if self.action == "create":
            return AppointmentCreateSerializer

        if self.action in ["update", "partial_update"]:
            if role == "receptionist":
                return AppointmentAssignSerializer
            if role == "doctor":
                return AppointmentDoctorUpdateSerializer

        return AppointmentSerializer

    def get_queryset(self):
        user = self.request.user
        role = user.role

        if role == "patient":
            return Appointment.objects.filter(created_by=user)
        if role == "doctor":
            return Appointment.objects.filter(doctor__user=user)
        if role == "receptionist":
            return Appointment.objects.filter(payment__status=Payment.Status.COMPLETED)
        if role == "admin":
            return Appointment.objects.all()

        return Appointment.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        appointment = serializer.save()
        Payment.objects.create(appointment=appointment, amount=appointment.fee)

        create_log(
            appointment=appointment,
            user=user,
            action="Appointment created (awaiting payment)",
        )
        _notify(
            user=user,
            title="Appointment Created",
            message="Your appointment has been created and is awaiting payment.",
            notification_type="appointment_booked",
            appointment=appointment,
            triggered_by=user,
        )

        doctor_user = getattr(appointment.doctor, "user", None)
        _notify(
            user=doctor_user,
            title="New Appointment Booked",
            message="A new appointment was booked and assigned to you.",
            notification_type="appointment_booked",
            appointment=appointment,
            triggered_by=user,
        )

    @extend_schema(tags=["Appointments"])
    @action(detail=True, methods=["post"])
    def pay(self, request, uuid=None):
        appointment = self.get_object()
        user = request.user

        if user != appointment.created_by:
            raise PermissionDenied("You can only pay your own appointment")

        payment = appointment.payment
        if payment.status == Payment.Status.COMPLETED:
            return Response({"message": "Already paid"})

        response = initiate_payment(payment, user, appointment)

        create_log(
            appointment=appointment,
            user=user,
            action=f"Payment initiated (ref: {payment.transaction_reference or 'pending'})",
        )
        _notify(
            user=user,
            title="Payment Initiated",
            message="Your payment request has been sent successfully.",
            notification_type="general",
            appointment=appointment,
            triggered_by=user,
        )

        return Response(
            {
                "message": "Payment initiated",
                "payment_uuid": payment.uuid,
                "gateway": response,
            }
        )

    @extend_schema(tags=["Appointments"])
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
            message="Your appointment has been cancelled.",
            notification_type="appointment_cancelled",
            appointment=appointment,
            triggered_by=user,
        )

        doctor_user = getattr(appointment.doctor, "user", None)
        _notify(
            user=doctor_user,
            title="Appointment Cancelled",
            message="A patient cancelled an appointment assigned to you.",
            notification_type="appointment_cancelled",
            appointment=appointment,
            triggered_by=user,
        )

        return Response({"message": "Appointment cancelled successfully"})

    def perform_update(self, serializer):
        old = self.get_object()
        user = self.request.user
        role = user.role

        if role == "patient":
            if old.created_by != user:
                raise PermissionDenied("Not your appointment")
            if old.payment.status == Payment.Status.COMPLETED:
                raise PermissionDenied("Cannot update after payment")

        if role == "doctor" and getattr(old.doctor, "user", None) != user:
            raise PermissionDenied("Not assigned to this appointment")

        if role == "receptionist" and old.payment.status != Payment.Status.COMPLETED:
            raise PermissionDenied("Cannot process unpaid appointment")

        updated = serializer.save()

        if role == "receptionist":
            if old.status != updated.status:
                create_log(updated, user, f"Status -> {updated.status}")
                _notify(
                    user=updated.created_by,
                    title="Appointment Status Updated",
                    message=f"Your appointment status is now '{updated.status}'.",
                    notification_type=(
                        "appointment_approved"
                        if updated.status == Appointment.Status.ACCEPTED
                        else "appointment_rejected"
                    ),
                    appointment=updated,
                    triggered_by=user,
                )

            if old.doctor != updated.doctor and updated.doctor:
                create_log(updated, user, f"Doctor assigned -> {updated.doctor}")
                _notify(
                    user=updated.doctor.user,
                    title="New Appointment Assigned",
                    message="A receptionist assigned you a new appointment.",
                    notification_type="appointment_booked",
                    appointment=updated,
                    triggered_by=user,
                )

            if old.appointment_date != updated.appointment_date:
                create_log(updated, user, f"Scheduled -> {updated.appointment_date}")
                _notify(
                    user=updated.created_by,
                    title="Appointment Rescheduled",
                    message=f"Your appointment was moved to {updated.appointment_date}.",
                    notification_type="appointment_rescheduled",
                    appointment=updated,
                    triggered_by=user,
                )

        elif role == "doctor":
            if old.status != updated.status and updated.status == "completed":
                create_log(updated, user, "Appointment completed")
                _notify(
                    user=updated.created_by,
                    title="Appointment Completed",
                    message="Your doctor marked your appointment as completed.",
                    notification_type="general",
                    appointment=updated,
                    triggered_by=user,
                )


@extend_schema_view(
    list=extend_schema(tags=["Illness Category"]),
    retrieve=extend_schema(tags=["Illness Category"]),
    create=extend_schema(tags=["Illness Category"]),
    update=extend_schema(tags=["Illness Category"]),
    partial_update=extend_schema(tags=["Illness Category"]),
    destroy=extend_schema(tags=["Illness Category"]),
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
                payment.payment_method = event_data.get("channel") or payment.payment_method
                payment.save(update_fields=["status", "payment_method", "updated_at"])
                create_log(appointment, None, f"Payment completed ({order_ref})")
                _notify(
                    user=appointment.created_by,
                    title="Payment Successful",
                    message="Your appointment payment was received successfully.",
                    notification_type="payment_success",
                    appointment=appointment,
                    triggered_by=appointment.created_by,
                )
                processed += 1
        elif event in {"PAYMENT FAILED", "FAILED"}:
            if payment.status != Payment.Status.FAILED:
                payment.status = Payment.Status.FAILED
                payment.payment_method = event_data.get("channel") or payment.payment_method
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
                )
                processed += 1

    return Response({"message": "Webhook processed", "processed": processed})
