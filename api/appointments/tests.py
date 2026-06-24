from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from api.accounts.models import DoctorProfile
from api.accounts.models import SystemSettings
from api.appointments.models import Appointment, IllnessCategory


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
        SystemSettings.objects.create(pk=1, appointment_fee=Decimal("4500.00"))

    @patch("api.notifications.services.send_notification_email")
    def test_patient_appointment_creation_triggers_email_notification(self, mock_send_email):
        self.client.force_authenticate(user=self.patient)

        response = self.client.post(
            reverse("appointment-list"),
            {
                "illness_category_uuid": str(self.category.uuid),
                "description": "Need a routine checkup",
                "preferred_date": date.today().isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(mock_send_email.called)
        self.assertEqual(mock_send_email.call_args.kwargs["recipient_email"], self.patient.email)
