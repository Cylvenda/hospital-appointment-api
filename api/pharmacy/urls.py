from rest_framework.routers import DefaultRouter

from .views import DispensingItemViewSet, DispensingViewSet, MedicineViewSet

router = DefaultRouter()
router.register(r"medicines", MedicineViewSet, basename="medicine")
router.register(r"dispensings", DispensingViewSet, basename="dispensing")
router.register(r"dispensing-items", DispensingItemViewSet, basename="dispensing-item")

urlpatterns = router.urls

