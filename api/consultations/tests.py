from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from api.accounts.models import DoctorProfile
from api.appointments.models import Appointment, IllnessCategory
from api.consultations.models import Consultation
from api.laboratory.models import LabRequest, LabTestType
from api.medical_records.models import Diagnosis


class ConsultationLabRequestTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.doctor_user = User.objects.create_user(
            email="doctor@example.com",
            phone="255700000030",
            password="password123",
            role="doctor",
            first_name="Doc",
            last_name="Tor",
        )
        self.doctor_profile = DoctorProfile.objects.create(
            user=self.doctor_user,
            license_number="DOC-902",
        )
        self.patient_user = User.objects.create_user(
            email="patient@example.com",
            phone="255700000031",
            password="password123",
            role="patient",
            first_name="Pat",
            last_name="Ient",
        )
        self.patient_profile = self.patient_user.patient_profile
        self.category = IllnessCategory.objects.create(name="Internal Medicine")
        self.appointment = Appointment.objects.create(
            category=self.category,
            created_by=self.patient_user,
            doctor=self.doctor_profile,
            fee=Decimal("5000.00"),
            preferred_date=date.today(),
        )
        self.consultation = Consultation.objects.create(
            appointment=self.appointment,
            doctor=self.doctor_profile,
            patient=self.patient_profile,
        )
        self.test_one = LabTestType.objects.create(name="CBC", description="Complete blood count")
        self.test_two = LabTestType.objects.create(name="LFT", description="Liver function test")
        self.client = APIClient()

    def test_doctor_can_create_multiple_lab_request_items(self):
        self.client.force_authenticate(user=self.doctor_user)

        response = self.client.post(
            f"/api/consultations/{self.consultation.uuid}/lab-requests/",
            {
                "items": [
                    {"test_type_uuid": str(self.test_one.uuid)},
                    {"test_type_uuid": str(self.test_two.uuid)},
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        lab_request = LabRequest.objects.get(consultation=self.consultation)
        self.assertEqual(lab_request.items.count(), 2)
        self.assertEqual(str(response.data["lab_request_uuid"]), str(lab_request.uuid))


class ConsultationDiagnosisTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.doctor_user = User.objects.create_user(
            email="doctor@example.com",
            phone="255700000040",
            password="password123",
            role="doctor",
            first_name="Doc",
            last_name="Tor",
        )
        self.doctor_profile = DoctorProfile.objects.create(
            user=self.doctor_user,
            license_number="DOC-903",
        )
        self.patient_user = User.objects.create_user(
            email="patient@example.com",
            phone="255700000041",
            password="password123",
            role="patient",
            first_name="Pat",
            last_name="Ient",
        )
        self.patient_profile = self.patient_user.patient_profile
        self.category = IllnessCategory.objects.create(name="Surgery")
        self.appointment = Appointment.objects.create(
            category=self.category,
            created_by=self.patient_user,
            doctor=self.doctor_profile,
            fee=Decimal("7000.00"),
            preferred_date=date.today(),
        )
        self.consultation = Consultation.objects.create(
            appointment=self.appointment,
            doctor=self.doctor_profile,
            patient=self.patient_profile,
        )
        self.client = APIClient()

    def test_doctor_can_add_diagnosis_even_when_notification_email_fails(self):
        self.client.force_authenticate(user=self.doctor_user)

        with patch("api.notifications.services.send_notification_email", side_effect=Exception("smtp down")):
            response = self.client.post(
                f"/api/consultations/{self.consultation.uuid}/diagnoses/",
                {
                    "disease_name": "Hypertension",
                    "icd10_code": "I10",
                    "description": "Persistent elevated blood pressure",
                    "type": "provisional",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        diagnosis = Diagnosis.objects.get(consultation=self.consultation)
        self.assertEqual(diagnosis.disease_name, "Hypertension")
