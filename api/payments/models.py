from django.db import models
from django.conf import settings

class WebhookAuditLog(models.Model):
    payment = models.ForeignKey(
        "appointments.Payment",
        on_delete=models.CASCADE,
        related_name="webhook_audits",
    )
    raw_payload = models.JSONField()
    headers = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    processing_result = models.CharField(max_length=32)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["payment", "processed_at"]),
        ]
        ordering = ["-processed_at"]
