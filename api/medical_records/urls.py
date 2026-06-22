from rest_framework.routers import DefaultRouter

from .views import DiagnosisViewSet, PatientMedicalRecordViewSet

router = DefaultRouter()
router.register(r"medical-records", PatientMedicalRecordViewSet, basename="medical-record")
router.register(r"diagnoses", DiagnosisViewSet, basename="diagnosis")

urlpatterns = router.urls

