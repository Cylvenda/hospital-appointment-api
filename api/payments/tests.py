from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import override_settings
from rest_framework.test import APITestCase

from api.accounts.models import DoctorAvailability, DoctorCategory, DoctorProfile, SystemSettings
from api.appointments.models import Appointment, IllnessCategory, Payment


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class PaymentCreateTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.patient = User.objects.create_user(
            email="payment-patient@example.com",
            phone="255700000030",
            password="password123",
            role="patient",
            first_name="Pat",
            last_name="Ient",
        )
        self.doctor_user = User.objects.create_user(
            email="payment-doctor@example.com",
            phone="255700000031",
            password="password123",
            role="doctor",
            first_name="Doc",
            last_name="Tor",
        )
        self.doctor_profile = DoctorProfile.objects.create(
            user=self.doctor_user,
            license_number="DOC-PAY-001",
        )
        self.category = IllnessCategory.objects.create(name="General Practice")
        DoctorCategory.objects.create(doctor=self.doctor_profile, category=self.category)
        self.appointment = Appointment.objects.create(
            category=self.category,
            created_by=self.patient,
            doctor=self.doctor_profile,
            fee=5000,
            preferred_date="2025-08-01",
            appointment_date="2025-08-01",
            start_time="08:00",
            end_time="08:30",
            status=Appointment.Status.PENDING,
        )
        Payment.objects.create(appointment=self.appointment, amount=self.appointment.fee)

    @patch("api.appointments.services.requests.post")
    def test_patient_can_initiate_payment(self, mock_post):
        appointment_id = self.appointment.id

        def side_effect(url, **kwargs):
            class R:
                status_code = 200

                def json(self_inner):
                    if "/generate-token" in str(url):
                        return {"token": "fake-token", "access_token": "fake-token"}
                    return {"orderReference": f"PAYID{appointment_id}UUIDABC123"}

            return R()

        mock_post.side_effect = side_effect

        self.client.force_authenticate(user=self.patient)

        response = self.client.post(
            reverse("payment-create"),
            {"appointment_uuid": str(self.appointment.uuid), "phone": "255700000030"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("payment_uuid", response.data)
        self.assertIn("reference", response.data)
        self.assertEqual(response.data["status"], "pending")

        payment = Payment.objects.get(uuid=response.data["payment_uuid"])
        self.assertEqual(payment.status, Payment.Status.PENDING)

    @patch("api.appointments.services.requests.post")
    def test_patient_cannot_pay_for_another_appointment(self, mock_post):
        other_user = get_user_model().objects.create_user(
            email="other@example.com",
            phone="255700000099",
            password="password123",
            role="patient",
        )
        self.client.force_authenticate(user=other_user)

        response = self.client.post(
            reverse("payment-create"),
            {"appointment_uuid": str(self.appointment.uuid), "phone": "255700000030"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class PaymentStatusTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.patient = User.objects.create_user(
            email="status-patient@example.com",
            phone="255700000040",
            password="password123",
            role="patient",
        )
        self.receptionist = User.objects.create_user(
            email="status-recep@example.com",
            phone="255700000041",
            password="password123",
            role="receptionist",
        )
        self.category = IllnessCategory.objects.create(name="General Practice")
        self.appointment = Appointment.objects.create(
            category=self.category,
            created_by=self.patient,
            fee=5000,
            preferred_date="2025-08-01",
            appointment_date="2025-08-01",
            start_time="08:00",
            end_time="08:30",
            status=Appointment.Status.PENDING,
        )
        self.payment = Payment.objects.create(
            appointment=self.appointment,
            amount=self.appointment.fee,
            status=Payment.Status.PENDING,
        )

    def test_patient_can_view_own_payment_status(self):
        self.client.force_authenticate(user=self.patient)

        response = self.client.get(
            reverse("payment-status", kwargs={"uuid": self.payment.uuid})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "pending")
        self.assertEqual(response.data["uuid"], str(self.payment.uuid))

    def test_receptionist_can_view_payment_status(self):
        self.client.force_authenticate(user=self.receptionist)

        response = self.client.get(
            reverse("payment-status", kwargs={"uuid": self.payment.uuid})
        )

        self.assertEqual(response.status_code, 200)

    def test_unauthorized_user_cannot_view_payment_status(self):
        stranger = get_user_model().objects.create_user(
            email="stranger@example.com",
            phone="255700000099",
            password="password123",
            role="patient",
        )
        self.client.force_authenticate(user=stranger)

        response = self.client.get(
            reverse("payment-status", kwargs={"uuid": self.payment.uuid})
        )

        self.assertEqual(response.status_code, 403)


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class PaymentWebhookTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.patient = User.objects.create_user(
            email="webhook-patient@example.com",
            phone="255700000050",
            password="password123",
            role="patient",
        )
        self.category = IllnessCategory.objects.create(name="General Practice")
        self.appointment = Appointment.objects.create(
            category=self.category,
            created_by=self.patient,
            doctor=None,
            fee=5000,
            preferred_date="2025-08-01",
            appointment_date="2025-08-01",
            start_time="08:00",
            end_time="08:30",
            status=Appointment.Status.PENDING,
        )
        self.payment = Payment.objects.create(
            appointment=self.appointment,
            amount=self.appointment.fee,
            status=Payment.Status.PENDING,
            transaction_reference="ORDER-123",
        )

    def test_webhook_success_transitions_pending_to_success(self):
        self.client.force_authenticate(user=self.patient)

        response = self.client.post(
            reverse("payment-webhook"),
            {
                "event": "PAYMENT RECEIVED",
                "data": {
                    "orderReference": "ORDER-123",
                    "transactionId": "TXN-999",
                    "channel": "M-PESA",
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.SUCCESS)
        self.assertIsNotNone(self.payment.paid_at)
        self.assertEqual(self.payment.gateway_transaction_id, "TXN-999")
        self.assertEqual(self.payment.payment_method, "M-PESA")
        self.assertEqual(self.payment.receipt_number, f"RCPT-{self.payment.uuid.hex[:8].upper()}-{self.payment.paid_at.strftime('%Y%m%d')}")

    def test_webhook_is_idempotent_for_duplicate_success(self):
        self.payment.status = Payment.Status.SUCCESS
        self.payment.save()

        response = self.client.post(
            reverse("payment-webhook"),
            {
                "event": "PAYMENT RECEIVED",
                "data": {
                    "orderReference": "ORDER-123",
                    "transactionId": "TXN-999",
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)

    def test_webhook_failure_transitions_pending_to_failed(self):
        response = self.client.post(
            reverse("payment-webhook"),
            {
                "event": "PAYMENT FAILED",
                "data": {
                    "orderReference": "ORDER-123",
                    "message": "Insufficient balance",
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.FAILED)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.CANCELLED)
