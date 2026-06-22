import uuid
from decimal import Decimal

from django.db import models
from django.utils import timezone


class Invoice(models.Model):
    class Status(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PARTIAL = "partial", "Partial"
        PAID = "paid", "Paid"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    patient = models.ForeignKey(
        "accounts.PatientProfile",
        on_delete=models.CASCADE,
        related_name="invoices",
    )
    consultation = models.ForeignKey(
        "consultations.Consultation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    invoice_number = models.CharField(max_length=50, unique=True, blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNPAID)
    issued_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-issued_at"]
        indexes = [
            models.Index(fields=["patient"]),
            models.Index(fields=["consultation"]),
            models.Index(fields=["status"]),
        ]

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            stamp = timezone.now().strftime("%Y%m%d")
            self.invoice_number = f"INV-{stamp}-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def recalculate_total(self, save=True):
        total = self.items.aggregate(total=models.Sum("amount")).get("total") or Decimal("0.00")
        self.total_amount = total
        if total <= 0:
            self.status = self.Status.UNPAID
            self.paid_at = None
        if save:
            self.save(update_fields=["total_amount", "status", "paid_at", "updated_at"])

    def __str__(self):
        return self.invoice_number or str(self.uuid)


class InvoiceItem(models.Model):
    class ItemType(models.TextChoices):
        CONSULTATION = "consultation", "Consultation"
        LABORATORY = "laboratory", "Laboratory"
        MEDICINE = "medicine", "Medicine"
        PROCEDURE = "procedure", "Procedure"
        OTHER = "other", "Other"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    item_type = models.CharField(max_length=20, choices=ItemType.choices)
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["invoice", "created_at"]

    def save(self, *args, **kwargs):
        self.amount = (self.quantity or 0) * (self.unit_price or 0)
        super().save(*args, **kwargs)
        self.invoice.recalculate_total(save=True)

    def delete(self, *args, **kwargs):
        invoice = self.invoice
        super().delete(*args, **kwargs)
        invoice.recalculate_total(save=True)

    def __str__(self):
        return f"{self.description} - {self.invoice}"

