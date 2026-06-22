from rest_framework.routers import DefaultRouter

from .views import LabRequestItemViewSet, LabRequestViewSet, LabResultViewSet, LabTestTypeViewSet

router = DefaultRouter()
router.register(r"lab-tests", LabTestTypeViewSet, basename="lab-test")
router.register(r"lab-requests", LabRequestViewSet, basename="lab-request")
router.register(r"lab-request-items", LabRequestItemViewSet, basename="lab-request-item")
router.register(r"lab-results", LabResultViewSet, basename="lab-result")

urlpatterns = router.urls

