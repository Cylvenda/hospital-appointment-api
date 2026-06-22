from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from api.accounts.models import DoctorProfile
from api.appointments.models import Appointment, IllnessCategory
from api.consultations.models import Consultation
from api.pharmacy.models import Medicine
from api.prescriptions.models import Prescription


class PharmacyWorkflowTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email="admin@example.com",
            phone="255700000001",
            password="password123",
            role="admin",
            first_name="Admin",
            last_name="User",
        )
        self.patient_user = User.objects.create_user(
            email="patient@example.com",
            phone="255700000002",
            password="password123",
            role="patient",
            first_name="Pat",
            last_name="Ient",
        )
        self.doctor_user = User.objects.create_user(
            email="doctor@example.com",
            phone="255700000003",
            password="password123",
            role="doctor",
            first_name="Doc",
            last_name="Tor",
        )
        self.doctor_profile = DoctorProfile.objects.create(
            user=self.doctor_user,
            license_number="DOC-001",
        )
        self.patient_profile = self.patient_user.patient_profile
        self.category = IllnessCategory.objects.create(name="General Medicine")
        self.appointment = Appointment.objects.create(
            category=self.category,
            created_by=self.patient_user,
            fee=Decimal("2500.00"),
            preferred_date=date.today(),
        )
        self.consultation = Consultation.objects.create(
            appointment=self.appointment,
            doctor=self.doctor_profile,
            patient=self.patient_profile,
        )
        self.prescription = Prescription.objects.create(
            consultation=self.consultation,
            doctor=self.doctor_profile,
            patient=self.patient_profile,
            notes="Take with food",
        )
        self.medicine = Medicine.objects.create(
            name="Amoxicillin",
            generic_name="Amoxicillin",
            unit_price=Decimal("1500.00"),
            stock_quantity=10,
        )
        self.client.force_authenticate(self.admin)

    def test_dispensing_status_transition_reduces_stock(self):
        dispensing_response = self.client.post(
            reverse("dispensing-list"),
            {
                "prescription_uuid": str(self.prescription.uuid),
                "status": "pending",
            },
            format="json",
        )
        self.assertEqual(dispensing_response.status_code, 201)
        dispensing_uuid = dispensing_response.data["uuid"]

        item_response = self.client.post(
            reverse("dispensing-item-list"),
            {
                "dispensing_uuid": dispensing_uuid,
                "medicine_uuid": str(self.medicine.uuid),
                "quantity": 3,
            },
            format="json",
        )
        self.assertEqual(item_response.status_code, 201)

        update_response = self.client.patch(
            reverse("dispensing-detail", kwargs={"uuid": dispensing_uuid}),
            {
                "status": "dispensed",
                "dispensed_at": "2026-06-22T10:00:00Z",
            },
            format="json",
        )
        self.assertEqual(update_response.status_code, 200)

        self.medicine.refresh_from_db()
        self.assertEqual(self.medicine.stock_quantity, 7)

    def test_cannot_dispense_more_than_available_stock(self):
        dispensing_response = self.client.post(
            reverse("dispensing-list"),
            {
                "prescription_uuid": str(self.prescription.uuid),
                "status": "pending",
            },
            format="json",
        )
        self.assertEqual(dispensing_response.status_code, 201)
        dispensing_uuid = dispensing_response.data["uuid"]

        item_response = self.client.post(
            reverse("dispensing-item-list"),
            {
                "dispensing_uuid": dispensing_uuid,
                "medicine_uuid": str(self.medicine.uuid),
                "quantity": 11,
            },
            format="json",
        )
        self.assertEqual(item_response.status_code, 201)

        update_response = self.client.patch(
            reverse("dispensing-detail", kwargs={"uuid": dispensing_uuid}),
            {
                "status": "dispensed",
                "dispensed_at": "2026-06-22T10:00:00Z",
            },
            format="json",
        )
        self.assertEqual(update_response.status_code, 400)
        self.assertIn("stock", update_response.data)

        self.medicine.refresh_from_db()
        self.assertEqual(self.medicine.stock_quantity, 10)
