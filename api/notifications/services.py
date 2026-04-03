from .models import Notification
from .task import send_notification_email


def create_and_send_notification(
    *,
    user,
    title,
    message,
    notification_type="general",
    appointment=None,
    triggered_by=None,
    send_email=True,
    extra_info=None,
):
    if not user:
        return None

    notification = Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        appointment_uuid=getattr(appointment, "uuid", None),
        triggered_by=triggered_by,
    )

    if send_email and user.email:
        send_notification_email(
            subject=title,
            message=message,
            recipient_email=user.email,
            extra_info=extra_info,
        )

    return notification
