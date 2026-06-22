import uuid

from django.db import models


class Prescription(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    consultation = models.ForeignKey(
        "consultations.Consultation",
        on_delete=models.CASCADE,
        related_name="prescriptions",
    )
    doctor = models.ForeignKey(
        "accounts.DoctorProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prescriptions",
    )
    patient = models.ForeignKey(
        "accounts.PatientProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prescriptions",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["consultation"]),
            models.Index(fields=["doctor"]),
            models.Index(fields=["patient"]),
        ]

    def __str__(self):
        return f"Prescription {self.uuid}"


class PrescriptionItem(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    prescription = models.ForeignKey(
        Prescription,
        on_delete=models.CASCADE,
        related_name="items",
    )
    medicine_name = models.CharField(max_length=255)
    dosage = models.CharField(max_length=100)
    frequency = models.CharField(max_length=100)
    duration = models.CharField(max_length=100)
    instructions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["prescription", "medicine_name"]

    def __str__(self):
        return f"{self.medicine_name} - {self.prescription}"

