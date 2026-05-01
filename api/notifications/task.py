import logging
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from datetime import datetime

logger = logging.getLogger(__name__)

def send_notification_email(
    subject,
    message,
    recipient_email,
    extra_info=None,
    appointment_details=None,
    action_details=None,
    cta_url=None,
    cta_label=None,
):
    context = {
        "title": subject,
        "message": message,
        "extra_info": extra_info,
        "appointment_details": appointment_details or [],
        "action_details": action_details or [],
        "cta_url": cta_url,
        "cta_label": cta_label,
        "app_name": getattr(settings, "SITE_NAME", "Patient Appointment"),
        "year": datetime.now().year,
    }

    # Render HTML template
    html_content = render_to_string("email/base_notification.html", context)

    email = EmailMultiAlternatives(
        subject=subject,
        body=message,  # fallback text
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient_email],
    )

    email.attach_alternative(html_content, "text/html")
    try:
        email.send()
        logger.info(f"Email sent successfully to {recipient_email} with subject '{subject}'")
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_email}: {e}")
        raise  # Re-raise to mark task as failed
