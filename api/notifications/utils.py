from .task import send_notification_email


def send_payment_email(user, subject, message):
    send_notification_email(
        subject=subject,
        message=message,
        recipient_email=user.email,
        cta_url="http://localhost:3000/patient-dashboard/payments",  # Example URL
        cta_label="View Payment Status"
    )
