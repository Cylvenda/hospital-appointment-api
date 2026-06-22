import uuid

from django.db import models


class PatientMedicalRecord(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    patient = models.OneToOneField(
        "accounts.PatientProfile",
        on_delete=models.CASCADE,
        related_name="medical_record",
    )
    blood_group = models.CharField(max_length=5, blank=True, null=True)
    allergies = models.TextField(blank=True)
    chronic_conditions = models.TextField(blank=True)
    weight = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    height = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    bmi = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["patient__user__last_name", "patient__user__first_name"]

    def __str__(self):
        return f"Medical Record - {self.patient}"


class Diagnosis(models.Model):
    class DiagnosisType(models.TextChoices):
        PROVISIONAL = "provisional", "Provisional"
        FINAL = "final", "Final"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    consultation = models.ForeignKey(
        "consultations.Consultation",
        on_delete=models.CASCADE,
        related_name="diagnoses",
    )
    disease_name = models.CharField(max_length=255)
    icd10_code = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    type = models.CharField(
        max_length=20,
        choices=DiagnosisType.choices,
        default=DiagnosisType.PROVISIONAL,
    )
    diagnosed_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-diagnosed_at", "-created_at"]
        indexes = [
            models.Index(fields=["consultation"]),
            models.Index(fields=["type"]),
            models.Index(fields=["disease_name"]),
        ]

    def __str__(self):
        return f"{self.disease_name} ({self.get_type_display()})"

