from django.test import TestCase
from rest_framework.test import APIClient
from api.appointments.models import IllnessCategory
from .models import DoctorProfile, User
from .serializers import PatientProfileSerializer


class PatientLocationTests(TestCase):
    def test_profile_stores_frontend_location_names_without_lookup_models(self):
        user = User.objects.create_user(
            email="patient@example.com",
            phone="+255700000001",
            password="StrongPass123!",
        )
        profile = user.patient_profile
        serializer = PatientProfileSerializer(
            profile,
            data={
                "dob": "1990-01-01",
                "gender": "Male",
                "education": "Bachelor Degree",
                "marital_status": "Single",
                "region": "Dar Es Salaam",
                "district": "Kinondoni",
                "ward": "Magomeni",
                "residence": "House 10",
                "next_of_kin": {
                    "name": "Relative Person",
                    "phone": "+255700000002",
                    "relationship": "Relative",
                },
            },
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        saved_profile = serializer.save()

        self.assertEqual(saved_profile.region, "Dar Es Salaam")
        self.assertEqual(saved_profile.district, "Kinondoni")
        self.assertEqual(saved_profile.ward, "Magomeni")
        self.assertTrue(saved_profile.is_profile_complete)

    def test_receptionist_can_open_selected_patient_profile(self):
        patient = User.objects.create_user(
            email="selected-patient@example.com",
            phone="+255700000003",
            password="StrongPass123!",
            role=User.Role.PATIENT,
        )
        patient.patient_profile.region = "Dodoma"
        patient.patient_profile.save()
        receptionist = User.objects.create_user(
            email="profile-reception@example.com",
            phone="+255700000004",
            password="StrongPass123!",
            role=User.Role.RECEPTIONIST,
        )
        client = APIClient()
        client.force_authenticate(user=receptionist)

        response = client.get(f"/api/admin/users/{patient.uuid}/")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(str(response.data["uuid"]), str(patient.uuid))
        self.assertEqual(response.data["patient_profile"]["region"], "Dodoma")


class DoctorProfileManagementTests(TestCase):
    def test_receptionist_can_assign_multiple_departments(self):
        receptionist = User.objects.create_user(
            email="reception@example.com",
            phone="+255700000010",
            password="StrongPass123!",
            role=User.Role.RECEPTIONIST,
        )
        doctor_user = User.objects.create_user(
            email="doctor@example.com",
            phone="+255700000011",
            password="StrongPass123!",
            role=User.Role.DOCTOR,
        )
        doctor = DoctorProfile.objects.create(
            user=doctor_user,
            license_number="DOC-MULTI",
        )
        department_one = IllnessCategory.objects.create(name="Cardiology")
        department_two = IllnessCategory.objects.create(name="General Medicine")
        client = APIClient()
        client.force_authenticate(user=receptionist)

        response = client.patch(
            f"/api/admin/doctors/{doctor.uuid}/",
            {
                "first_name": "Updated",
                "category_uuids": [
                    str(department_one.uuid),
                    str(department_two.uuid),
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        doctor.refresh_from_db()
        doctor.user.refresh_from_db()
        self.assertEqual(doctor.user.first_name, "Updated")
        self.assertEqual(doctor.doctorcategory_set.count(), 2)
