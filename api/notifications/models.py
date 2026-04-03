import uuid
from django.db import models
from django.conf import settings


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        APPOINTMENT_BOOKED = "appointment_booked", "Appointment Booked"
        APPOINTMENT_APPROVED = "appointment_approved", "Appointment Approved"
        APPOINTMENT_REJECTED = "appointment_rejected", "Appointment Rejected"
        APPOINTMENT_RESCHEDULED = "appointment_rescheduled", "Appointment Rescheduled"
        APPOINTMENT_CANCELLED = "appointment_cancelled", "Appointment Cancelled"
        APPOINTMENT_REMINDER = "appointment_reminder", "Appointment Reminder"
        PAYMENT_SUCCESS = "payment_success", "Payment Success"
        GENERAL = "general", "General"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )

    title = models.CharField(max_length=255)
    message = models.TextField()

    notification_type = models.CharField(
        max_length=50,
        choices=NotificationType.choices,
        default=NotificationType.GENERAL,
    )

    # Appointment reference
    appointment_uuid = models.UUIDField(null=True, blank=True)

    # Optional: who triggered the notification (doctor/receptionist/patient)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_notifications",
    )

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} - {self.title}"
