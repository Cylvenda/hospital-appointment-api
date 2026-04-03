from background_task import background
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from datetime import datetime


@background(schedule=1)
def send_notification_email(subject, message, recipient_email, extra_info=None):
    context = {
        "title": subject,
        "message": message,
        "extra_info": extra_info,
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
    email.send()
