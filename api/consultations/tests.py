from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from api.accounts.models import DoctorProfile
from api.appointments.models import Appointment, IllnessCategory
from api.consultations.models import Consultation
from api.laboratory.models import LabRequest, LabResult, LabTestType
from api.medical_records.models import Diagnosis
from api.notifications.models import Notification
from api.prescriptions.models import Prescription, PrescriptionItem


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

    @patch("api.notifications.services.send_notification_email")
    def test_doctor_can_create_multiple_lab_request_items(self, mock_send_email):
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
        self.appointment.refresh_from_db()
        self.assertEqual(
            self.appointment.status,
            Appointment.Status.WAITING_FOR_LABORATORY,
        )
        notification = Notification.objects.filter(
            user=self.patient_user,
            notification_type=Notification.NotificationType.LAB_REQUESTED,
        ).latest("created_at")
        self.assertEqual(notification.appointment_uuid, self.appointment.uuid)
        recipient_emails = [
            call.kwargs["recipient_email"]
            for call in mock_send_email.call_args_list
        ]
        self.assertIn(self.patient_user.email, recipient_emails)

    @patch("api.notifications.services.send_notification_email")
    def test_completed_laboratory_work_returns_patient_to_same_doctor(
        self,
        mock_send_email,
    ):
        lab_user = get_user_model().objects.create_user(
            email="lab@example.com",
            phone="255700000032",
            password="password123",
            role="lab_tech",
        )
        lab_request = LabRequest.objects.create(
            consultation=self.consultation,
            doctor=self.doctor_profile,
            patient=self.patient_profile,
        )
        item_one = lab_request.items.create(test_type=self.test_one)
        item_two = lab_request.items.create(test_type=self.test_two)
        self.client.force_authenticate(user=lab_user)

        for item in (item_one, item_two):
            response = self.client.post(
                "/api/lab-results/",
                {
                    "request_item_uuid": str(item.uuid),
                    "result": "Within reference range",
                    "remarks": "Verified",
                },
                format="json",
            )
            self.assertEqual(response.status_code, 201, response.data)

        response = self.client.patch(
            f"/api/lab-requests/{lab_request.uuid}/",
            {"status": LabRequest.Status.COMPLETED},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(LabResult.objects.filter(request_item__lab_request=lab_request).count(), 2)
        self.appointment.refresh_from_db()
        self.assertEqual(
            self.appointment.status,
            Appointment.Status.BACK_TO_DOCTOR,
        )
        self.assertEqual(self.appointment.doctor, self.doctor_profile)
        patient_notifications = Notification.objects.filter(
            user=self.patient_user,
            notification_type=Notification.NotificationType.LAB_RESULT_AVAILABLE,
        )
        self.assertTrue(patient_notifications.exists())
        self.assertTrue(
            patient_notifications.filter(
                title="Laboratory Tests Complete",
                appointment_uuid=self.appointment.uuid,
            ).exists()
        )
        recipient_emails = [
            call.kwargs["recipient_email"]
            for call in mock_send_email.call_args_list
        ]
        self.assertIn(self.patient_user.email, recipient_emails)


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

    def test_doctor_can_export_complete_encounter_as_pdf_and_docx(self):
        Diagnosis.objects.create(
            consultation=self.consultation,
            disease_name="Hypertension",
            icd10_code="I10",
            description="Persistent elevated blood pressure",
            type=Diagnosis.DiagnosisType.FINAL,
        )
        prescription = Prescription.objects.create(
            consultation=self.consultation,
            doctor=self.doctor_profile,
            patient=self.patient_profile,
            notes="Review after seven days",
        )
        PrescriptionItem.objects.create(
            prescription=prescription,
            medicine_name="Amlodipine",
            dosage="5 mg",
            frequency="Once daily",
            duration="30 days",
            instructions="Take after breakfast",
        )
        self.client.force_authenticate(user=self.doctor_user)

        pdf_response = self.client.get(
            f"/api/consultations/{self.consultation.uuid}/export/?file_format=pdf"
        )
        docx_response = self.client.get(
            f"/api/consultations/{self.consultation.uuid}/export/?file_format=docx"
        )

        self.assertEqual(
            pdf_response.status_code,
            200,
            getattr(pdf_response, "data", pdf_response.content[:200]),
        )
        self.assertEqual(pdf_response["Content-Type"], "application/pdf")
        self.assertTrue(pdf_response.content.startswith(b"%PDF"))
        self.assertIn("clinical_record_", pdf_response["Content-Disposition"])

        self.assertEqual(docx_response.status_code, 200)
        self.assertEqual(
            docx_response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.assertTrue(docx_response.content.startswith(b"PK"))

    def test_export_rejects_unsupported_format(self):
        self.client.force_authenticate(user=self.doctor_user)

        response = self.client.get(
            f"/api/consultations/{self.consultation.uuid}/export/?file_format=csv"
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("detail", response.data)
