from django.conf import settings
from .models import Notification
from .task import send_notification_email


def _display_value(value, fallback="Not available"):
    if value in (None, "", []):
        return fallback
    return str(value)


def _format_date(value):
    if not value:
        return "Not scheduled yet"
    return value.strftime("%B %d, %Y")


def _format_time_range(start_time, end_time):
    if not start_time and not end_time:
        return "Not scheduled yet"
    start = start_time.strftime("%I:%M %p") if start_time else "TBD"
    end = end_time.strftime("%I:%M %p") if end_time else "TBD"
    return f"{start} - {end}"


def _build_appointment_details(appointment):
    if not appointment:
        return []

    doctor_name = None
    if getattr(appointment, "doctor", None) and getattr(appointment.doctor, "user", None):
        doctor_name = appointment.doctor.user.full_name or appointment.doctor.user.email

    payment = getattr(appointment, "payment", None)

    details = [
        {"label": "Appointment ID", "value": str(appointment.uuid)},
        {"label": "Service", "value": _display_value(getattr(appointment.category, "name", None))},
        {"label": "Status", "value": appointment.get_status_display()},
        {"label": "Preferred Date", "value": _format_date(appointment.preferred_date)},
        {"label": "Scheduled Date", "value": _format_date(appointment.appointment_date)},
        {"label": "Time", "value": _format_time_range(appointment.start_time, appointment.end_time)},
        {"label": "Doctor", "value": _display_value(doctor_name, "Not assigned yet")},
        {"label": "Fee", "value": f"TZS {appointment.fee}"},
    ]

    if payment:
        details.append({"label": "Payment Status", "value": payment.get_status_display()})
        if payment.payment_method:
            details.append({"label": "Payment Method", "value": payment.payment_method})

    if appointment.description:
        details.append({"label": "Your Note", "value": appointment.description})

    if appointment.cancel_reason:
        details.append({"label": "Cancellation Reason", "value": appointment.cancel_reason})

    return details


def _build_action_details(triggered_by):
    if not triggered_by:
        return []

    actor_name = triggered_by.full_name or triggered_by.email
    return [
        {"label": "Updated By", "value": actor_name},
        {"label": "Role", "value": str(triggered_by.role).replace("_", " ").title()},
    ]


def _build_frontend_url():
    domain = getattr(settings, "DOMAIN", None) or "localhost:3000"
    protocol = getattr(settings, "EMAIL_FRONTEND_PROTOCOL", None) or "http"
    return f"{protocol}://{domain}"


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
    cta_url=None,
    cta_label=None,
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
            appointment_details=_build_appointment_details(appointment),
            action_details=_build_action_details(triggered_by),
            cta_url=cta_url or f"{_build_frontend_url()}/login",
            cta_label=cta_label or "Open PAMS",
        )

    return notification
