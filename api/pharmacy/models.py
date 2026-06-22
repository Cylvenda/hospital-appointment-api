import uuid

from django.conf import settings
from django.db import models


class Medicine(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=255, unique=True)
    generic_name = models.CharField(max_length=255, blank=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stock_quantity = models.PositiveIntegerField(default=0)
    expiry_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Dispensing(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DISPENSED = "dispensed", "Dispensed"
        CANCELLED = "cancelled", "Cancelled"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    prescription = models.OneToOneField(
        "prescriptions.Prescription",
        on_delete=models.CASCADE,
        related_name="dispensing",
    )
    pharmacist = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dispensings",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    dispensed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Dispensing {self.uuid}"


class DispensingItem(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    dispensing = models.ForeignKey(Dispensing, on_delete=models.CASCADE, related_name="items")
    medicine = models.ForeignKey(Medicine, on_delete=models.PROTECT, related_name="dispensing_items")
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("dispensing", "medicine")

    def __str__(self):
        return f"{self.medicine} x {self.quantity}"

