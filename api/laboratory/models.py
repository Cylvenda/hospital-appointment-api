import uuid

from django.conf import settings
from django.db import models


class LabTestType(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class LabRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SAMPLE_COLLECTED = "sample_collected", "Sample Collected"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    consultation = models.ForeignKey(
        "consultations.Consultation",
        on_delete=models.CASCADE,
        related_name="lab_requests",
    )
    doctor = models.ForeignKey(
        "accounts.DoctorProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lab_requests",
    )
    patient = models.ForeignKey(
        "accounts.PatientProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lab_requests",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-requested_at"]
        indexes = [
            models.Index(fields=["consultation"]),
            models.Index(fields=["doctor"]),
            models.Index(fields=["patient"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Lab Request {self.uuid}"


class LabRequestItem(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    lab_request = models.ForeignKey(
        LabRequest,
        on_delete=models.CASCADE,
        related_name="items",
    )
    test_type = models.ForeignKey(
        LabTestType,
        on_delete=models.PROTECT,
        related_name="lab_request_items",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("lab_request", "test_type")

    def __str__(self):
        return f"{self.test_type} - {self.lab_request}"


class LabResult(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    request_item = models.OneToOneField(
        LabRequestItem,
        on_delete=models.CASCADE,
        related_name="result",
    )
    result = models.TextField(blank=True)
    remarks = models.TextField(blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_lab_results",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Lab Result - {self.request_item}"
