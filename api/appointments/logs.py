from api.appointments.models import AppointmentLog


def create_log(appointment, user, action):
    AppointmentLog.objects.create(
        appointment=appointment, performed_by=user, action=action
    )
