from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from api.accounts.models import DoctorAvailability, DoctorUnavailableDate

from .models import Appointment, AppointmentQueue


BLOCKING_STATUSES = {
    Appointment.Status.PENDING,
    Appointment.Status.CONFIRMED,
    Appointment.Status.CHECKED_IN,
    Appointment.Status.WAITING_IN_QUEUE,
    Appointment.Status.IN_CONSULTATION,
    Appointment.Status.WAITING_FOR_LABORATORY,
    Appointment.Status.LABORATORY_IN_PROGRESS,
    Appointment.Status.LABORATORY_RESULTS_READY,
    Appointment.Status.BACK_TO_DOCTOR,
}


def get_available_slots(doctor, appointment_date):
    if not doctor.is_available or not doctor.user.is_active:
        return []
    if appointment_date < timezone.localdate():
        return []
    if DoctorUnavailableDate.objects.filter(
        doctor=doctor,
        date=appointment_date,
    ).exists():
        return []

    schedule = DoctorAvailability.objects.filter(
        doctor=doctor,
        day_of_week=appointment_date.weekday(),
        is_active=True,
    ).first()
    if not schedule:
        return []

    booked = Appointment.objects.filter(
        doctor=doctor,
        appointment_date=appointment_date,
        status__in=BLOCKING_STATUSES,
    )
    maximum = doctor.max_appointments_per_day
    if maximum is not None and booked.count() >= maximum:
        return []

    booked_times = set(booked.values_list("start_time", flat=True))
    duration = timedelta(minutes=doctor.consultation_duration)
    cursor = datetime.combine(appointment_date, schedule.start_time)
    schedule_end = datetime.combine(appointment_date, schedule.end_time)
    break_start = (
        datetime.combine(appointment_date, schedule.break_start_time)
        if schedule.break_start_time
        else None
    )
    break_end = (
        datetime.combine(appointment_date, schedule.break_end_time)
        if schedule.break_end_time
        else None
    )
    slots = []

    while cursor + duration <= schedule_end:
        slot_end = cursor + duration
        overlaps_break = (
            break_start is not None
            and break_end is not None
            and cursor < break_end
            and slot_end > break_start
        )
        if not overlaps_break and cursor.time() not in booked_times:
            slots.append(
                {
                    "start_time": cursor.time().strftime("%H:%M"),
                    "end_time": slot_end.time().strftime("%H:%M"),
                }
            )
            if maximum is not None and len(slots) + booked.count() >= maximum:
                break
        cursor = slot_end

    return slots


def validate_slot(doctor, appointment_date, start_time):
    slots = get_available_slots(doctor, appointment_date)
    selected = next(
        (slot for slot in slots if slot["start_time"] == start_time.strftime("%H:%M")),
        None,
    )
    if not selected:
        raise ValidationError(
            {"start_time": "This appointment slot is no longer available."}
        )
    return selected


@transaction.atomic
def check_in_appointment(appointment):
    if not appointment.doctor or not appointment.appointment_date:
        raise ValidationError("A scheduled doctor and date are required for check-in.")
    if appointment.appointment_date != timezone.localdate():
        raise ValidationError("Only today's appointments can be checked in.")
    if appointment.status not in {
        Appointment.Status.CONFIRMED,
        Appointment.Status.CHECKED_IN,
    }:
        raise ValidationError("Only confirmed appointments can be checked in.")

    existing = AppointmentQueue.objects.select_for_update().filter(
        appointment=appointment
    ).first()
    if existing:
        return existing

    latest = (
        AppointmentQueue.objects.select_for_update()
        .filter(
            doctor=appointment.doctor,
            queue_date=appointment.appointment_date,
        )
        .order_by("-queue_number")
        .first()
    )
    queue_entry = AppointmentQueue.objects.create(
        appointment=appointment,
        doctor=appointment.doctor,
        queue_date=appointment.appointment_date,
        queue_number=(latest.queue_number + 1) if latest else 1,
    )
    appointment.status = Appointment.Status.WAITING_IN_QUEUE
    appointment.save(update_fields=["status", "updated_at"])
    return queue_entry
