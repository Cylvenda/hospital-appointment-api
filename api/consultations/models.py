import uuid

from django.db import models


class Consultation(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    appointment = models.OneToOneField(
        "appointments.Appointment",
        on_delete=models.CASCADE,
        related_name="consultation",
    )
    doctor = models.ForeignKey(
        "accounts.DoctorProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consultations",
    )
    patient = models.ForeignKey(
        "accounts.PatientProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consultations",
    )
    chief_complaint = models.TextField(blank=True)
    history_of_present_illness = models.TextField(blank=True)
    physical_examination = models.TextField(blank=True)
    provisional_diagnosis = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-started_at", "-created_at"]
        indexes = [
            models.Index(fields=["doctor"]),
            models.Index(fields=["patient"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Consultation {self.uuid} - {self.appointment}"

