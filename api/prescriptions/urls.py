from rest_framework.routers import DefaultRouter

from .views import PrescriptionItemViewSet, PrescriptionViewSet

router = DefaultRouter()
router.register(r"prescriptions", PrescriptionViewSet, basename="prescription")
router.register(r"prescription-items", PrescriptionItemViewSet, basename="prescription-item")

urlpatterns = router.urls

