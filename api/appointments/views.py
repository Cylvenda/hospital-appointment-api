from rest_framework import viewsets
from rest_framework.decorators import action, api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from datetime import date, datetime, timedelta
from drf_spectacular.utils import extend_schema, extend_schema_view
import re
from api.accounts.models import (
    DoctorAvailability,
    DoctorProfile,
    DoctorUnavailableDate,
)
from api.appointments.models import (
    Appointment,
    AppointmentQueue,
    IllnessCategory,
    Payment,
)
from api.appointments.serializers import (
    AppointmentSerializer,
    AppointmentCreateSerializer,
    AppointmentAssignSerializer,
    AppointmentPatientUpdateSerializer,
    AppointmentDoctorUpdateSerializer,
    DoctorOptionSerializer,
    DoctorScheduleSerializer,
    DoctorUnavailableDateSerializer,
    AppointmentQueueSerializer,
    IllnessCategorySerializer,
)
from api.notifications.services import create_and_send_notification
from .logs import create_log
from .services import initiate_payment
from .scheduling import check_in_appointment, get_available_slots, validate_slot

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
            if role == "patient":
                return AppointmentPatientUpdateSerializer

        return AppointmentSerializer

    def get_queryset(self):
        user = self.request.user
        role = user.role
        queue_name = self.request.query_params.get("queue")
        base_queryset = Appointment.objects.select_related(
            "created_by__patient_profile__next_of_kin",
            "category",
            "doctor__user",
            "payment",
        )

        if role == "patient":
            queryset = base_queryset.filter(created_by=user)
        elif role == "doctor":
            queryset = base_queryset.filter(doctor__user=user)
        elif role == "receptionist":
            queryset = base_queryset.all()
        elif role == "admin":
            queryset = base_queryset.all()
        else:
            return Appointment.objects.none()

        if queue_name:
            queryset = Appointment.apply_queue_filter(queryset, role, queue_name)

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(appointment_id__icontains=search)

        return queryset.distinct().order_by("-created_at")

    @action(detail=False, methods=["get"], url_path="queues")
    def queues(self, request):
        role = request.user.role
        base_queryset = Appointment.objects.all()

        if role == "patient":
            base_queryset = base_queryset.filter(created_by=request.user)
        elif role == "doctor":
            base_queryset = base_queryset.filter(doctor__user=request.user)
        elif role in {"receptionist", "admin"}:
            base_queryset = base_queryset.all()
        else:
            raise PermissionDenied("You do not have permission to view appointment queues")

        available_queues = Appointment.available_queues_for_role(role)
        data = [
            {
                "name": queue_name,
                "label": queue_label,
                "count": Appointment.apply_queue_filter(base_queryset, role, queue_name).distinct().count(),
            }
            for queue_name, queue_label in available_queues.items()
        ]
        return Response(data)

    @action(detail=False, methods=["get"], url_path="doctors")
    def doctors(self, request):
        queryset = (
            DoctorProfile.objects.select_related("user")
            .prefetch_related("doctorcategory_set__category")
            .filter(is_available=True, user__is_active=True)
        )
        category_uuid = request.query_params.get("category_uuid")
        if category_uuid:
            queryset = queryset.filter(
                doctorcategory__category__uuid=category_uuid
            )
        serializer = DoctorOptionSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="available-days")
    def available_days(self, request):
        doctor_uuid = request.query_params.get("doctor_uuid")
        if not doctor_uuid:
            raise ValidationError({"doctor_uuid": "Doctor is required."})
        doctor = DoctorProfile.objects.select_related("user").filter(
            uuid=doctor_uuid,
            is_available=True,
            user__is_active=True,
        ).first()
        if not doctor:
            raise ValidationError({"doctor_uuid": "Doctor was not found."})

        try:
            days = min(max(int(request.query_params.get("days", 30)), 1), 90)
            start = date.fromisoformat(
                request.query_params.get("from", timezone.localdate().isoformat())
            )
        except (TypeError, ValueError):
            raise ValidationError({"date": "Use a valid ISO date."})

        available = []
        for offset in range(days):
            candidate = start + timedelta(days=offset)
            slots = get_available_slots(doctor, candidate)
            if slots:
                available.append(
                    {
                        "date": candidate,
                        "slot_count": len(slots),
                    }
                )
        return Response(available)

    @action(detail=False, methods=["get"], url_path="available-slots")
    def available_slots(self, request):
        doctor_uuid = request.query_params.get("doctor_uuid")
        appointment_date = request.query_params.get("date")
        if not doctor_uuid or not appointment_date:
            raise ValidationError("Doctor and date are required.")
        doctor = DoctorProfile.objects.select_related("user").filter(
            uuid=doctor_uuid,
            is_available=True,
            user__is_active=True,
        ).first()
        if not doctor:
            raise ValidationError({"doctor_uuid": "Doctor was not found."})
        try:
            selected_date = date.fromisoformat(appointment_date)
        except ValueError:
            raise ValidationError({"date": "Use a valid ISO date."})
        return Response(get_available_slots(doctor, selected_date))

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
            message="Your appointment request has been created successfully and is now waiting for payment confirmation.",
            notification_type="appointment_booked",
            appointment=appointment,
            triggered_by=user,
            extra_info="After payment is completed, the hospital team can continue processing your appointment request.",
        )

        doctor_user = getattr(appointment.doctor, "user", None)
        if doctor_user:
            _notify(
                user=doctor_user,
                title="New Appointment Booked",
                message="A new appointment request has been booked and assigned to you For review.",
                notification_type="appointment_booked",
                appointment=appointment,
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
        if payment.status == Payment.Status.SUCCESS:
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

    @action(detail=True, methods=["post"], url_path="mark-paid")
    def mark_paid(self, request, uuid=None):
        if request.user.role not in {"admin", "receptionist"}:
            raise PermissionDenied(
                "Only admin or reception staff can confirm an offline payment."
            )

        with transaction.atomic():
            appointment = (
                Appointment.objects.select_for_update()
                .select_related("created_by")
                .get(pk=self.get_object().pk)
            )
            payment = Payment.objects.select_for_update().get(
                appointment=appointment
            )

            if payment.status == Payment.Status.SUCCESS:
                return Response(
                    AppointmentSerializer(
                        appointment,
                        context={"request": request},
                    ).data
                )

            if appointment.status != Appointment.Status.PENDING:
                raise ValidationError(
                    "Only a pending appointment can be marked as paid."
                )
            if not (
                appointment.doctor_id
                and appointment.appointment_date
                and appointment.start_time
                and appointment.end_time
            ):
                raise ValidationError(
                    "The appointment must have a doctor and complete time slot."
                )

            payment_method = request.data.get("payment_method") or "manual"
            allowed_methods = {
                "manual",
                "cash",
                "mobile_money",
                "bank_transfer",
                "insurance",
            }
            if (
                not isinstance(payment_method, str)
                or payment_method not in allowed_methods
            ):
                raise ValidationError(
                    {"payment_method": "Choose a supported payment method."}
                )
            payment.status = Payment.Status.SUCCESS
            payment.payment_method = payment_method
            if not payment.transaction_reference:
                payment.transaction_reference = f"MANUAL-{payment.uuid}"
            payment.save(
                update_fields=[
                    "status",
                    "payment_method",
                    "transaction_reference",
                    "updated_at",
                ]
            )

            appointment.status = Appointment.Status.CONFIRMED
            appointment.save(update_fields=["status", "updated_at"])

            create_log(
                appointment=appointment,
                user=request.user,
                action=f"Payment marked completed manually ({payment_method})",
            )
            _notify(
                user=appointment.created_by,
                title="Payment Confirmed",
                message=(
                    "Hospital staff confirmed your payment. "
                    "Your appointment is now booked."
                ),
                notification_type="payment_success",
                appointment=appointment,
                triggered_by=request.user,
                extra_info=(
                    "Please arrive before your scheduled time for check-in."
                ),
            )

        return Response(
            AppointmentSerializer(
                appointment,
                context={"request": request},
            ).data
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, uuid=None):
        appointment = self.get_object()
        user = request.user
        cancel_reason = (
            request.data.get("reason")
            or request.data.get("cancel_reason")
            or ""
        ).strip()

        if user != appointment.created_by:
            raise PermissionDenied("You can only cancel your appointment")

        appointment.status = Appointment.Status.CANCELLED
        appointment.cancel_reason = cancel_reason
        appointment.save(update_fields=["status", "cancel_reason", "updated_at"])

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

        return Response(AppointmentSerializer(appointment, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="check-in")
    def check_in(self, request, uuid=None):
        if request.user.role not in {"admin", "receptionist"}:
            raise PermissionDenied("Only reception staff can check in patients.")
        appointment = self.get_object()
        queue_entry = check_in_appointment(appointment)
        create_log(
            appointment,
            request.user,
            f"Checked in as queue #{queue_entry.queue_number}",
        )
        return Response(
            AppointmentSerializer(appointment, context={"request": request}).data
        )

    @action(detail=True, methods=["post"])
    def reschedule(self, request, uuid=None):
        if request.user.role not in {"admin", "receptionist"}:
            raise PermissionDenied("Only admin or reception staff can reschedule.")
        appointment = self.get_object()
        if not appointment.doctor:
            raise ValidationError("A doctor must be assigned before rescheduling.")
        try:
            appointment_date = date.fromisoformat(request.data.get("date", ""))
            start_time = datetime.strptime(
                request.data.get("start_time", ""),
                "%H:%M",
            ).time()
        except (TypeError, ValueError):
            raise ValidationError("A valid date and start time are required.")
        if (
            appointment.appointment_date == appointment_date
            and appointment.start_time == start_time
        ):
            raise ValidationError("Choose a different appointment slot.")

        selected = validate_slot(appointment.doctor, appointment_date, start_time)
        old_schedule = f"{appointment.appointment_date} {appointment.start_time}"
        appointment.appointment_date = appointment_date
        appointment.preferred_date = appointment_date
        appointment.start_time = start_time
        appointment.end_time = datetime.strptime(
            selected["end_time"],
            "%H:%M",
        ).time()
        appointment.status = Appointment.Status.CONFIRMED
        appointment.save(
            update_fields=[
                "appointment_date",
                "preferred_date",
                "start_time",
                "end_time",
                "status",
                "updated_at",
            ]
        )
        AppointmentQueue.objects.filter(appointment=appointment).delete()
        create_log(
            appointment,
            request.user,
            f"Rescheduled from {old_schedule}",
        )
        _notify(
            user=appointment.created_by,
            title="Appointment Rescheduled",
            message="Your appointment has been moved to a new doctor schedule slot.",
            notification_type="appointment_rescheduled",
            appointment=appointment,
            triggered_by=request.user,
        )
        return Response(
            AppointmentSerializer(appointment, context={"request": request}).data
        )

    @action(detail=True, methods=["post"], url_path="start-consultation")
    def start_consultation(self, request, uuid=None):
        if request.user.role != "doctor":
            raise PermissionDenied("Only the assigned doctor can start consultation.")
        appointment = self.get_object()
        if appointment.doctor.user != request.user:
            raise PermissionDenied("This appointment is assigned to another doctor.")
        if appointment.status not in {
            Appointment.Status.WAITING_IN_QUEUE,
            Appointment.Status.BACK_TO_DOCTOR,
        }:
            raise ValidationError("The patient is not ready for consultation.")
        appointment.status = Appointment.Status.IN_CONSULTATION
        appointment.save(update_fields=["status", "updated_at"])
        if hasattr(appointment, "queue_entry"):
            appointment.queue_entry.called_at = timezone.now()
            appointment.queue_entry.save(update_fields=["called_at"])
        create_log(appointment, request.user, "Consultation started")
        return Response(
            AppointmentSerializer(appointment, context={"request": request}).data
        )

    @action(detail=False, methods=["post"], url_path="call-next")
    def call_next(self, request):
        if request.user.role != "doctor":
            raise PermissionDenied("Only doctors can call the next patient.")
        queue_entry = (
            AppointmentQueue.objects.select_related("appointment", "doctor__user")
            .filter(
                doctor__user=request.user,
                queue_date=timezone.localdate(),
                appointment__status=Appointment.Status.WAITING_IN_QUEUE,
            )
            .order_by("queue_number")
            .first()
        )
        if not queue_entry:
            return Response({"detail": "There are no patients waiting."}, status=404)
        appointment = queue_entry.appointment
        appointment.status = Appointment.Status.IN_CONSULTATION
        appointment.save(update_fields=["status", "updated_at"])
        queue_entry.called_at = timezone.now()
        queue_entry.save(update_fields=["called_at"])
        return Response(
            AppointmentSerializer(appointment, context={"request": request}).data
        )

    @action(detail=False, methods=["get"], url_path="today-queue")
    def today_queue(self, request):
        queryset = AppointmentQueue.objects.select_related(
            "appointment__created_by",
            "doctor__user",
        ).filter(queue_date=timezone.localdate())
        if request.user.role == "doctor":
            queryset = queryset.filter(doctor__user=request.user)
        elif request.user.role not in {"admin", "receptionist"}:
            raise PermissionDenied("You cannot view today's queue.")
        return Response(AppointmentQueueSerializer(queryset, many=True).data)

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
            and old.payment.status != Payment.Status.SUCCESS
        ):
            raise PermissionDenied("Cannot process unpaid appointment")

        updated = serializer.save()

        if role in ["receptionist", "admin"]:
            if old_status != updated.status:
                create_log(updated, user, f"Status -> {updated.status}")
                status_label = Appointment.status_label_for_context(
                    updated.status,
                    getattr(updated.payment, "status", None),
                    audience="patient",
                )
                notification_type = (
                    "appointment_approved"
                    if updated.status == Appointment.Status.CONFIRMED
                    else "appointment_cancelled"
                    if updated.status == Appointment.Status.CANCELLED
                    else "appointment_rejected"
                )
                _notify(
                    user=updated.created_by,
                    title="Appointment Status Updated",
                    message=f"Your appointment status has been updated to '{status_label}'.",
                    notification_type=notification_type,
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
                if updated.status == Appointment.Status.CONFIRMED:
                    create_log(updated, user, "Appointment confirmed")
                    _notify(
                        user=updated.created_by,
                        title="Appointment Accepted",
                        message="Your appointment has been confirmed.",
                        notification_type="appointment_approved",
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


class SchedulePermissionMixin:
    permission_classes = [IsAuthenticated]

    def _ensure_schedule_manager(self):
        if self.request.user.role not in {"admin", "receptionist"}:
            raise PermissionDenied("Only admin or reception staff can manage schedules.")

    def perform_create(self, serializer):
        self._ensure_schedule_manager()
        serializer.save()

    def perform_update(self, serializer):
        self._ensure_schedule_manager()
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_schedule_manager()
        instance.delete()


class DoctorScheduleViewSet(SchedulePermissionMixin, viewsets.ModelViewSet):
    serializer_class = DoctorScheduleSerializer
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def get_queryset(self):
        queryset = DoctorAvailability.objects.select_related(
            "doctor__user"
        ).order_by("doctor__user__first_name", "day_of_week")
        doctor_uuid = self.request.query_params.get("doctor_uuid")
        if doctor_uuid:
            queryset = queryset.filter(doctor__uuid=doctor_uuid)
        return queryset


class DoctorUnavailableDateViewSet(
    SchedulePermissionMixin,
    viewsets.ModelViewSet,
):
    serializer_class = DoctorUnavailableDateSerializer
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def get_queryset(self):
        queryset = DoctorUnavailableDate.objects.select_related(
            "doctor__user"
        ).order_by("date")
        doctor_uuid = self.request.query_params.get("doctor_uuid")
        if doctor_uuid:
            queryset = queryset.filter(doctor__uuid=doctor_uuid)
        return queryset


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
            if payment.status != Payment.Status.SUCCESS:
                payment.status = Payment.Status.SUCCESS
                payment.payment_method = (
                    event_data.get("channel") or payment.payment_method
                )
                payment.save(update_fields=["status", "payment_method", "updated_at"])
                if (
                    appointment.doctor_id
                    and appointment.appointment_date
                    and appointment.start_time
                    and appointment.status == Appointment.Status.PENDING
                ):
                    appointment.status = Appointment.Status.CONFIRMED
                    appointment.save(update_fields=["status", "updated_at"])
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
            # A delayed gateway failure must never reverse a payment that was
            # already confirmed by the gateway or hospital staff.
            if payment.status not in {
                Payment.Status.FAILED,
                Payment.Status.SUCCESS,
            }:
                payment.status = Payment.Status.FAILED
                payment.payment_method = (
                    event_data.get("channel") or payment.payment_method
                )
                payment.save(update_fields=["status", "payment_method", "updated_at"])
                if appointment.status == Appointment.Status.PENDING:
                    appointment.status = Appointment.Status.CANCELLED
                    appointment.save(update_fields=["status", "updated_at"])
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
