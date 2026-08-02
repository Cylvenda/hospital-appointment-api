from datetime import date, time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from api.accounts.models import DoctorAvailability, DoctorCategory, DoctorProfile
from api.accounts.models import SystemSettings
from api.appointments.models import (
    Appointment,
    AppointmentQueue,
    IllnessCategory,
    Payment,
)


class AppointmentCancelTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.patient = User.objects.create_user(
            email="patient@example.com",
            phone="255700000020",
            password="password123",
            role="patient",
            first_name="Pat",
            last_name="Ient",
        )
        self.doctor_user = User.objects.create_user(
            email="doctor@example.com",
            phone="255700000021",
            password="password123",
            role="doctor",
            first_name="Doc",
            last_name="Tor",
        )
        self.doctor_profile = DoctorProfile.objects.create(
            user=self.doctor_user,
            license_number="DOC-901",
        )
        self.category = IllnessCategory.objects.create(name="General Practice")
        self.appointment = Appointment.objects.create(
            category=self.category,
            created_by=self.patient,
            doctor=self.doctor_profile,
            fee=Decimal("3000.00"),
            preferred_date=date.today(),
        )

    def test_patient_can_cancel_appointment_via_dedicated_endpoint(self):
        self.client.force_authenticate(user=self.patient)

        response = self.client.post(
            reverse("appointment-cancel", kwargs={"uuid": self.appointment.uuid}),
            {"reason": "No longer needed"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.CANCELLED)
        self.assertEqual(self.appointment.cancel_reason, "No longer needed")
        self.assertEqual(response.data["status"], Appointment.Status.CANCELLED)


class AppointmentNotificationTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.patient = User.objects.create_user(
            email="patient@example.com",
            phone="255700000022",
            password="password123",
            role="patient",
            first_name="Pat",
            last_name="Ient",
        )
        self.doctor_user = User.objects.create_user(
            email="doctor@example.com",
            phone="255700000023",
            password="password123",
            role="doctor",
            first_name="Doc",
            last_name="Tor",
        )
        self.doctor_profile = DoctorProfile.objects.create(
            user=self.doctor_user,
            license_number="DOC-902",
        )
        self.category = IllnessCategory.objects.create(name="Family Medicine")
        DoctorCategory.objects.create(
            doctor=self.doctor_profile,
            category=self.category,
        )
        self.appointment_date = date.today() + timedelta(days=1)
        DoctorAvailability.objects.create(
            doctor=self.doctor_profile,
            day_of_week=self.appointment_date.weekday(),
            start_time=time(8, 0),
            end_time=time(10, 0),
        )
        SystemSettings.objects.create(pk=1, appointment_fee=Decimal("4500.00"))

    @patch("api.notifications.services.send_notification_email")
    def test_patient_appointment_creation_triggers_email_notification(self, mock_send_email):
        self.client.force_authenticate(user=self.patient)

        response = self.client.post(
            reverse("appointment-list"),
            {
                "illness_category_uuid": str(self.category.uuid),
                "doctor_uuid": str(self.doctor_profile.uuid),
                "appointment_date": self.appointment_date.isoformat(),
                "start_time": "08:00",
                "description": "Need a routine checkup",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(mock_send_email.called)
        recipient_emails = [
            call.kwargs["recipient_email"]
            for call in mock_send_email.call_args_list
        ]
        self.assertIn(self.patient.email, recipient_emails)


class DoctorScheduleAndQueueTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.patient = User.objects.create_user(
            email="scheduled-patient@example.com",
            phone="255700000050",
            password="password123",
            role="patient",
        )
        self.doctor_user = User.objects.create_user(
            email="scheduled-doctor@example.com",
            phone="255700000051",
            password="password123",
            role="doctor",
        )
        self.doctor = DoctorProfile.objects.create(
            user=self.doctor_user,
            license_number="DOC-SCHEDULE",
            consultation_duration=30,
        )
        self.category = IllnessCategory.objects.create(name="Scheduled Care")
        DoctorCategory.objects.create(doctor=self.doctor, category=self.category)
        self.appointment_date = date.today() + timedelta(days=1)
        DoctorAvailability.objects.create(
            doctor=self.doctor,
            day_of_week=self.appointment_date.weekday(),
            start_time=time(8, 0),
            end_time=time(10, 0),
            break_start_time=time(9, 0),
            break_end_time=time(9, 30),
        )
        SystemSettings.objects.update_or_create(
            pk=1,
            defaults={"appointment_fee": Decimal("5000.00")},
        )

    def test_available_slots_exclude_breaks_and_booked_slots(self):
        Appointment.objects.create(
            category=self.category,
            created_by=self.patient,
            doctor=self.doctor,
            fee=Decimal("5000.00"),
            preferred_date=self.appointment_date,
            appointment_date=self.appointment_date,
            start_time=time(8, 30),
            end_time=time(9, 0),
            status=Appointment.Status.CONFIRMED,
        )
        self.client.force_authenticate(user=self.patient)

        response = self.client.get(
            reverse("appointment-available-slots"),
            {
                "doctor_uuid": self.doctor.uuid,
                "date": self.appointment_date.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [slot["start_time"] for slot in response.data],
            ["08:00", "09:30"],
        )

    def test_patient_can_filter_doctors_by_department(self):
        other_category = IllnessCategory.objects.create(name="Other Care")
        self.client.force_authenticate(user=self.patient)

        matching = self.client.get(
            reverse("appointment-doctors"),
            {"category_uuid": self.category.uuid},
        )
        not_matching = self.client.get(
            reverse("appointment-doctors"),
            {"category_uuid": other_category.uuid},
        )

        self.assertEqual(matching.status_code, 200)
        self.assertEqual(len(matching.data), 1)
        self.assertEqual(str(matching.data[0]["uuid"]), str(self.doctor.uuid))
        self.assertEqual(not_matching.status_code, 200)
        self.assertEqual(not_matching.data, [])

    def test_doctor_search_by_appointment_id_includes_patient_profile(self):
        profile = self.patient.patient_profile
        profile.gender = "Female"
        profile.region = "Dar Es Salaam"
        profile.district = "Kinondoni"
        profile.ward = "Magomeni"
        profile.blood_group = "O+"
        profile.insurance_provider = "NHIF"
        profile.save()
        appointment = Appointment.objects.create(
            category=self.category,
            created_by=self.patient,
            doctor=self.doctor,
            fee=Decimal("5000.00"),
            preferred_date=self.appointment_date,
            appointment_date=self.appointment_date,
            start_time=time(8, 0),
            end_time=time(8, 30),
            status=Appointment.Status.CONFIRMED,
            description="Persistent headache",
        )
        Payment.objects.create(
            appointment=appointment,
            amount=appointment.fee,
            status=Payment.Status.SUCCESS,
        )
        self.client.force_authenticate(user=self.doctor_user)

        response = self.client.get(
            reverse("appointment-list"),
            {"search": appointment.appointment_id},
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data), 1)
        result = response.data[0]
        self.assertEqual(str(result["patient_uuid"]), str(self.patient.uuid))
        self.assertEqual(result["patient_phone"], self.patient.phone)
        self.assertEqual(result["patient_profile"]["patient_id"], profile.patient_id)
        self.assertEqual(result["patient_profile"]["ward"], "Magomeni")
        self.assertEqual(result["patient_profile"]["blood_group"], "O+")
        self.assertEqual(result["description"], "Persistent headache")

    def test_repeated_schedule_creation_updates_existing_weekday(self):
        admin = get_user_model().objects.create_user(
            email="schedule-admin@example.com",
            phone="255700000053",
            password="password123",
            role="admin",
        )
        self.client.force_authenticate(user=admin)
        schedule = DoctorAvailability.objects.get(
            doctor=self.doctor,
            day_of_week=self.appointment_date.weekday(),
        )
        payload = {
            "doctor_uuid": str(self.doctor.uuid),
            "day_of_week": self.appointment_date.weekday(),
            "start_time": "07:30",
            "end_time": "11:30",
            "break_start_time": None,
            "break_end_time": None,
            "is_active": True,
        }

        response = self.client.post(
            reverse("doctor-schedule-list"),
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(
            DoctorAvailability.objects.filter(
                doctor=self.doctor,
                day_of_week=self.appointment_date.weekday(),
            ).count(),
            1,
        )
        schedule.refresh_from_db()
        self.assertEqual(schedule.start_time, time(7, 30))
        self.assertEqual(schedule.end_time, time(11, 30))

    def test_patient_books_a_generated_slot(self):
        self.client.force_authenticate(user=self.patient)

        response = self.client.post(
            reverse("appointment-list"),
            {
                "illness_category_uuid": self.category.uuid,
                "doctor_uuid": self.doctor.uuid,
                "appointment_date": self.appointment_date,
                "start_time": "08:00",
                "description": "Scheduled visit",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        appointment = Appointment.objects.get(uuid=response.data["uuid"])
        self.assertEqual(appointment.end_time, time(8, 30))
        self.assertEqual(appointment.status, Appointment.Status.PENDING)

    def test_patient_update_rejects_legacy_preferred_dates(self):
        appointment = Appointment.objects.create(
            category=self.category,
            created_by=self.patient,
            doctor=self.doctor,
            fee=Decimal("5000.00"),
            preferred_date=self.appointment_date,
            appointment_date=self.appointment_date,
            start_time=time(8, 0),
            end_time=time(8, 30),
            status=Appointment.Status.PENDING,
            description="Original note",
        )
        self.client.force_authenticate(user=self.patient)

        response = self.client.patch(
            reverse("appointment-detail", kwargs={"uuid": appointment.uuid}),
            {
                "description": "Updated note",
                "preferred_date": self.appointment_date.isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("preferred_date", response.data)

    def test_receptionist_can_mark_pending_appointment_as_paid(self):
        receptionist = get_user_model().objects.create_user(
            email="payment-reception@example.com",
            phone="255700000054",
            password="password123",
            role="receptionist",
        )
        appointment = Appointment.objects.create(
            category=self.category,
            created_by=self.patient,
            doctor=self.doctor,
            fee=Decimal("5000.00"),
            preferred_date=self.appointment_date,
            appointment_date=self.appointment_date,
            start_time=time(8, 0),
            end_time=time(8, 30),
            status=Appointment.Status.PENDING,
        )
        payment = Payment.objects.create(
            appointment=appointment,
            amount=appointment.fee,
        )
        self.client.force_authenticate(user=receptionist)

        response = self.client.post(
            reverse("appointment-mark-paid", kwargs={"uuid": appointment.uuid}),
            {"payment_method": "cash"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        appointment.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.CONFIRMED)
        self.assertEqual(payment.status, payment.Status.SUCCESS)
        self.assertEqual(payment.payment_method, "cash")
        self.assertEqual(response.data["payment_status"], "success")

    def test_admin_can_mark_pending_appointment_as_paid(self):
        admin = get_user_model().objects.create_user(
            email="payment-admin@example.com",
            phone="255700000055",
            password="password123",
            role="admin",
        )
        appointment = Appointment.objects.create(
            category=self.category,
            created_by=self.patient,
            doctor=self.doctor,
            fee=Decimal("5000.00"),
            preferred_date=self.appointment_date,
            appointment_date=self.appointment_date,
            start_time=time(9, 30),
            end_time=time(10, 0),
            status=Appointment.Status.PENDING,
        )
        Payment.objects.create(
            appointment=appointment,
            amount=appointment.fee,
        )
        self.client.force_authenticate(user=admin)

        response = self.client.post(
            reverse("appointment-mark-paid", kwargs={"uuid": appointment.uuid}),
            {"payment_method": "bank_transfer"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        appointment.refresh_from_db()
        appointment.payment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.CONFIRMED)
        self.assertEqual(appointment.payment.status, Payment.Status.SUCCESS)
        self.assertEqual(appointment.payment.payment_method, "bank_transfer")

    def test_patient_cannot_manually_mark_appointment_as_paid(self):
        appointment = Appointment.objects.create(
            category=self.category,
            created_by=self.patient,
            doctor=self.doctor,
            fee=Decimal("5000.00"),
            preferred_date=self.appointment_date,
            appointment_date=self.appointment_date,
            start_time=time(8, 0),
            end_time=time(8, 30),
            status=Appointment.Status.PENDING,
        )
        Payment.objects.create(
            appointment=appointment,
            amount=appointment.fee,
        )
        self.client.force_authenticate(user=self.patient)

        response = self.client.post(
            reverse("appointment-mark-paid", kwargs={"uuid": appointment.uuid}),
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_reception_check_in_assigns_queue_number(self):
        receptionist = get_user_model().objects.create_user(
            email="reception@example.com",
            phone="255700000052",
            password="password123",
            role="receptionist",
        )
        appointment = Appointment.objects.create(
            category=self.category,
            created_by=self.patient,
            doctor=self.doctor,
            fee=Decimal("5000.00"),
            preferred_date=date.today(),
            appointment_date=date.today(),
            start_time=time(8, 0),
            end_time=time(8, 30),
            status=Appointment.Status.CONFIRMED,
        )
        self.client.force_authenticate(user=receptionist)

        response = self.client.post(
            reverse("appointment-check-in", kwargs={"uuid": appointment.uuid})
        )

        self.assertEqual(response.status_code, 200, response.data)
        queue_entry = AppointmentQueue.objects.get(appointment=appointment)
        self.assertEqual(queue_entry.queue_number, 1)
        self.assertEqual(
            response.data["status"],
            Appointment.Status.WAITING_IN_QUEUE,
        )

    def test_receptionist_reschedules_only_to_generated_slot(self):
        receptionist = get_user_model().objects.create_user(
            email="reschedule@example.com",
            phone="255700000053",
            password="password123",
            role="receptionist",
        )
        appointment = Appointment.objects.create(
            category=self.category,
            created_by=self.patient,
            doctor=self.doctor,
            fee=Decimal("5000.00"),
            preferred_date=self.appointment_date,
            appointment_date=self.appointment_date,
            start_time=time(8, 0),
            end_time=time(8, 30),
            status=Appointment.Status.CONFIRMED,
        )
        self.client.force_authenticate(user=receptionist)

        response = self.client.post(
            reverse(
                "appointment-reschedule",
                kwargs={"uuid": appointment.uuid},
            ),
            {
                "date": self.appointment_date.isoformat(),
                "start_time": "09:30",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        appointment.refresh_from_db()
        self.assertEqual(appointment.start_time, time(9, 30))
        self.assertEqual(appointment.end_time, time(10, 0))
        self.assertEqual(appointment.status, Appointment.Status.CONFIRMED)
