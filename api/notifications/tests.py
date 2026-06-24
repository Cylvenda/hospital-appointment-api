from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from api.accounts.models import DoctorProfile
from api.appointments.models import Appointment, IllnessCategory
from api.notifications.services import create_and_send_notification


class NotificationEmailTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.patient = User.objects.create_user(
            email="patient@example.com",
            phone="255700000010",
            password="password123",
            role="patient",
            first_name="Pat",
            last_name="Ient",
        )
        self.doctor_user = User.objects.create_user(
            email="doctor@example.com",
            phone="255700000011",
            password="password123",
            role="doctor",
            first_name="Doc",
            last_name="Tor",
        )
        self.doctor_profile = DoctorProfile.objects.create(
            user=self.doctor_user,
            license_number="DOC-900",
        )
        self.category = IllnessCategory.objects.create(name="General Medicine")
        self.appointment = Appointment.objects.create(
            category=self.category,
            created_by=self.patient,
            doctor=self.doctor_profile,
            fee=Decimal("2500.00"),
            preferred_date=date.today(),
        )

    @patch("api.notifications.services.send_notification_email")
    def test_appointment_email_uses_public_appointment_id(self, mock_send_email):
        create_and_send_notification(
            user=self.patient,
            title="Appointment Updated",
            message="Your appointment was updated.",
            notification_type="appointment_rescheduled",
            appointment=self.appointment,
            triggered_by=self.doctor_user,
        )

        mock_send_email.assert_called_once()
        kwargs = mock_send_email.call_args.kwargs
        self.assertIn(self.appointment.appointment_id, kwargs["subject"])
        self.assertIn(self.appointment.appointment_id, kwargs["message"])
        appointment_details = kwargs["appointment_details"]

        self.assertTrue(any(item["label"] == "Appointment ID" for item in appointment_details))
        self.assertTrue(
            any(
                item["label"] == "Appointment ID"
                and item["value"] == self.appointment.appointment_id
                for item in appointment_details
            )
        )
        self.assertTrue(
            any(
                item["label"] == "Reference UUID"
                and item["value"] == str(self.appointment.uuid)
                for item in appointment_details
            )
        )

    @patch("api.notifications.services.send_notification_email", side_effect=Exception("smtp down"))
    def test_notification_email_failure_does_not_block_notification_creation(self, mock_send_email):
        notification = create_and_send_notification(
            user=self.patient,
            title="Appointment Updated",
            message="Your appointment was updated.",
            notification_type="appointment_rescheduled",
            appointment=self.appointment,
            triggered_by=self.doctor_user,
        )

        self.assertIsNotNone(notification)
        self.assertEqual(notification.title, "Appointment Updated")
        self.assertEqual(notification.user, self.patient)
        self.assertEqual(mock_send_email.call_count, 1)
