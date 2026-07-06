import uuid
import random
import string
from django.db import models
from django.conf import settings
from django.utils import timezone


# Illness Categories
class IllnessCategory(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


# Appointment
class Appointment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CHECKED_IN = "checked_in", "Checked In"
        WAITING_IN_QUEUE = "waiting_in_queue", "Waiting in Queue"
        IN_CONSULTATION = "in_consultation", "In Consultation"
        WAITING_FOR_LABORATORY = "waiting_for_laboratory", "Waiting for Laboratory"
        LABORATORY_IN_PROGRESS = "laboratory_in_progress", "Laboratory In Progress"
        LABORATORY_RESULTS_READY = "laboratory_results_ready", "Laboratory Results Ready"
        BACK_TO_DOCTOR = "back_to_doctor", "Back to Doctor"
        CANCELLED = "cancelled", "Cancelled"
        NO_SHOW = "no_show", "No Show"
        RESCHEDULED = "rescheduled", "Rescheduled"
        COMPLETED = "completed", "Completed"

    ROLE_STATUS_TRANSITIONS = {
        "admin": {
            Status.PENDING: {Status.CONFIRMED, Status.CANCELLED},
            Status.CONFIRMED: {
                Status.CHECKED_IN,
                Status.NO_SHOW,
                Status.RESCHEDULED,
                Status.CANCELLED,
            },
            Status.CHECKED_IN: {Status.WAITING_IN_QUEUE, Status.CANCELLED},
            Status.WAITING_IN_QUEUE: {Status.IN_CONSULTATION, Status.NO_SHOW},
            Status.IN_CONSULTATION: {
                Status.WAITING_FOR_LABORATORY,
                Status.COMPLETED,
            },
            Status.BACK_TO_DOCTOR: {
                Status.IN_CONSULTATION,
                Status.WAITING_FOR_LABORATORY,
                Status.COMPLETED,
            },
        },
        "receptionist": {
            Status.PENDING: {Status.CONFIRMED, Status.CANCELLED},
            Status.CONFIRMED: {
                Status.CHECKED_IN,
                Status.NO_SHOW,
                Status.RESCHEDULED,
                Status.CANCELLED,
            },
            Status.CHECKED_IN: {Status.WAITING_IN_QUEUE, Status.CANCELLED},
        },
        "doctor": {
            Status.WAITING_IN_QUEUE: {Status.IN_CONSULTATION},
            Status.IN_CONSULTATION: {
                Status.WAITING_FOR_LABORATORY,
                Status.COMPLETED,
            },
            Status.BACK_TO_DOCTOR: {
                Status.IN_CONSULTATION,
                Status.WAITING_FOR_LABORATORY,
                Status.COMPLETED,
            },
        },
        "patient": {},
    }

    ROLE_QUEUES = {
        "admin": {
            "all": "All Appointments",
            "daily-schedule": "Daily Schedule",
            "completed": "Completed",
            "cancelled": "Cancelled",
        },
        "receptionist": {
            "new": "New Appointments",
            "awaiting-payment": "Awaiting Payment",
            "awaiting-doctor-assignment": "Booking Confirmation",
            "today": "Today's Schedule",
            "checked-in": "Checked-In Patients",
            "completed": "Completed",
            "cancelled": "Cancelled",
        },
        "doctor": {
            "assigned": "Today's Queue",
            "waiting-for-consultation": "Waiting in Queue",
            "in-consultation": "In Consultation",
            "waiting-for-doctor-review": "Waiting for Doctor Review",
            "completed": "Completed Consultations",
        },
        "patient": {
            "upcoming": "Upcoming",
            "completed": "Completed",
            "cancelled": "Cancelled",
            "payment-history": "Payment History",
        },
    }

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    appointment_id = models.CharField(max_length=6, unique=True, blank=True, null=True)
    doctor = models.ForeignKey(
        "accounts.DoctorProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
    )
    category = models.ForeignKey(IllnessCategory, on_delete=models.CASCADE)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_appointments",
    )
    fee = models.DecimalField(max_digits=10, decimal_places=2)
    preferred_date = models.DateField()
    preferred_date_2 = models.DateField(blank=True, null=True)
    preferred_date_3 = models.DateField(blank=True, null=True)
    appointment_date = models.DateField(blank=True, null=True)
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    status = models.CharField(max_length=32, choices=Status, default=Status.PENDING)
    cancel_reason = models.TextField(null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    diagnosis = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("doctor", "appointment_date", "start_time")
        indexes = [
            models.Index(fields=["doctor"]),
            models.Index(fields=["category"]),
            models.Index(fields=["appointment_date"]),
            models.Index(fields=["status"]),
        ]

    def save(self, *args, **kwargs):
        if not self.appointment_id:
            while True:
                aid = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                if not Appointment.objects.filter(appointment_id=aid).exists():
                    self.appointment_id = aid
                    break
        super().save(*args, **kwargs)

    @classmethod
    def can_transition_status(cls, role, current_status, next_status):
        if not role or not current_status or not next_status:
            return False

        if current_status == next_status:
            return True

        role_transitions = cls.ROLE_STATUS_TRANSITIONS.get(role, {})
        allowed_targets = role_transitions.get(current_status, set())
        return next_status in allowed_targets

    @classmethod
    def available_queues_for_role(cls, role):
        return cls.ROLE_QUEUES.get(role, {})

    @classmethod
    def apply_queue_filter(cls, queryset, role, queue_name):
        queue_name = (queue_name or "").strip().lower()
        if not queue_name:
            return queryset

        today = timezone.localdate()
        current_time = timezone.localtime().time()

        if role == "admin":
            if queue_name == "daily-schedule":
                return queryset.filter(appointment_date=today)
            if queue_name == "completed":
                return queryset.filter(status=cls.Status.COMPLETED)
            if queue_name == "cancelled":
                return queryset.filter(status=cls.Status.CANCELLED)
            return queryset

        if role == "receptionist":
            if queue_name == "new":
                return queryset.filter(
                    status=cls.Status.PENDING,
                    payment__status=Payment.Status.PENDING,
                    created_at__date=today,
                )
            if queue_name == "awaiting-payment":
                return queryset.filter(
                    status=cls.Status.PENDING,
                    payment__status=Payment.Status.PENDING,
                )
            if queue_name == "awaiting-doctor-assignment":
                return queryset.filter(
                    status=cls.Status.PENDING,
                    payment__status=Payment.Status.COMPLETED,
                )
            if queue_name == "today":
                return queryset.filter(
                    appointment_date=today,
                    status__in=[
                        cls.Status.CONFIRMED,
                        cls.Status.CHECKED_IN,
                        cls.Status.WAITING_IN_QUEUE,
                        cls.Status.IN_CONSULTATION,
                        cls.Status.WAITING_FOR_LABORATORY,
                        cls.Status.LABORATORY_IN_PROGRESS,
                        cls.Status.BACK_TO_DOCTOR,
                    ],
                )
            if queue_name == "checked-in":
                return queryset.filter(
                    appointment_date=today,
                    status__in=[
                        cls.Status.CHECKED_IN,
                        cls.Status.WAITING_IN_QUEUE,
                        cls.Status.IN_CONSULTATION,
                    ],
                )
            if queue_name == "completed":
                return queryset.filter(status=cls.Status.COMPLETED)
            if queue_name == "cancelled":
                return queryset.filter(status=cls.Status.CANCELLED)
            return queryset

        if role == "doctor":
            if queue_name == "assigned":
                return queryset.filter(
                    status__in=[
                        cls.Status.CONFIRMED,
                        cls.Status.WAITING_IN_QUEUE,
                        cls.Status.IN_CONSULTATION,
                        cls.Status.BACK_TO_DOCTOR,
                    ]
                )
            if queue_name == "waiting-for-consultation":
                return queryset.filter(
                    status=cls.Status.WAITING_IN_QUEUE,
                    appointment_date=today,
                )
            if queue_name == "in-consultation":
                return queryset.filter(status=cls.Status.IN_CONSULTATION)
            if queue_name == "waiting-for-doctor-review":
                return queryset.filter(status=cls.Status.BACK_TO_DOCTOR)
            if queue_name == "completed":
                return queryset.filter(status=cls.Status.COMPLETED)
            return queryset

        if role == "patient":
            if queue_name == "upcoming":
                return queryset.exclude(
                    status__in=[
                        cls.Status.COMPLETED,
                        cls.Status.CANCELLED,
                        cls.Status.NO_SHOW,
                        cls.Status.RESCHEDULED,
                    ]
                )
            if queue_name == "completed":
                return queryset.filter(status=cls.Status.COMPLETED)
            if queue_name == "cancelled":
                return queryset.filter(status=cls.Status.CANCELLED)
            if queue_name == "payment-history":
                return queryset.exclude(payment__status=Payment.Status.PENDING)
            return queryset

        return queryset

    @classmethod
    def queue_counts_for_queryset(cls, queryset, role):
        counts = {}
        for queue_name in cls.available_queues_for_role(role).keys():
            counts[queue_name] = cls.apply_queue_filter(queryset, role, queue_name).distinct().count()
        return counts

    @classmethod
    def status_label_for_context(cls, status, payment_status=None, audience=None):
        audience = audience or "default"

        if status == cls.Status.PENDING:
            if payment_status == "completed":
                if audience in {"patient", "default"}:
                    return "Confirming booking"
                return "Payment confirmed"

            if audience in {"receptionist", "admin"}:
                return "Awaiting payment"

            return "Waiting for payment"

        if status == cls.Status.CONFIRMED:
            if audience == "doctor":
                return "Ready for review"
            if audience == "patient":
                return "Scheduled"
            return "Scheduled"

        if status == cls.Status.COMPLETED:
            return "Completed"
        if status == cls.Status.CANCELLED:
            return "Cancelled"
        if status == cls.Status.NO_SHOW:
            return "No Show"
        if status == cls.Status.RESCHEDULED:
            return "Rescheduled"

        return status.title() if status else "Unknown"

    @classmethod
    def status_summary_for_context(cls, status, payment_status=None, audience=None):
        audience = audience or "default"

        if status == cls.Status.PENDING:
            if payment_status == "completed":
                if audience == "doctor":
                    return "The appointment is paid and ready for a clinical review."
                if audience == "patient":
                    return "Your payment has been received and the booking is being confirmed."
                return "The appointment is paid and its selected slot is being confirmed."
            if audience == "doctor":
                return "The appointment is still waiting on payment before it reaches your queue."
            return "The appointment is waiting for payment confirmation."

        if status == cls.Status.CONFIRMED:
            if audience == "patient":
                return "Your selected clinician and visit time are confirmed."
            if audience == "doctor":
                return "This appointment is assigned to you and ready for assessment."
            return "The appointment is paid and scheduled."

        if status == cls.Status.COMPLETED:
            return "The visit is complete and clinical notes are recorded."
        if status == cls.Status.CANCELLED:
            return "The appointment was cancelled and removed from the active queue."
        if status == cls.Status.NO_SHOW:
            return "The patient did not attend the scheduled appointment."
        if status == cls.Status.RESCHEDULED:
            return "The original slot was replaced by a new schedule."

        return ""


# Appointment Logs
class AppointmentLog(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    appointment = models.ForeignKey(
        Appointment, on_delete=models.CASCADE, related_name="logs"
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    action = models.CharField(max_length=255)
    old_status = models.CharField(max_length=32, blank=True, null=True)
    new_status = models.CharField(max_length=32, blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)


class AppointmentQueue(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.CASCADE,
        related_name="queue_entry",
    )
    doctor = models.ForeignKey(
        "accounts.DoctorProfile",
        on_delete=models.CASCADE,
        related_name="queue_entries",
    )
    queue_date = models.DateField()
    queue_number = models.PositiveIntegerField()
    checked_in_at = models.DateTimeField(default=timezone.now)
    called_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["queue_date", "doctor", "queue_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["doctor", "queue_date", "queue_number"],
                name="unique_doctor_daily_queue_number",
            )
        ]

    def __str__(self):
        return f"{self.doctor} #{self.queue_number} on {self.queue_date}"


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        FAILED = "failed", "Failed"
        COMPLETED = "completed", "Completed"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    appointment = models.OneToOneField(
        Appointment, on_delete=models.CASCADE, related_name="payment"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status, default=Status.PENDING)
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    transaction_reference = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment {self.uuid} for {self.appointment}"
