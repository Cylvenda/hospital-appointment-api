from django.core.mail import send_mail


def send_payment_email(user, subject, message):
    send_mail(
        subject,
        message,
        "your-email@gmail.com",
        [user.email],
        fail_silently=False,
    )
