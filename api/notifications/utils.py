from django.conf import settings
from .task import send_notification_email


def send_payment_email(user, subject, message):
    domain = getattr(settings, "EMAIL_FRONTEND_DOMAIN", None)
    protocol = getattr(settings, "EMAIL_FRONTEND_PROTOCOL", None) or "https"
    cta_url = f"{protocol}://{domain}/patient-dashboard/payments"
    send_notification_email(
        subject=subject,
        message=message,
        recipient_email=user.email,
        cta_url=cta_url,
        cta_label="View Payment Status"
    )
