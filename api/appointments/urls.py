from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import AppointmentViewSet, IllnessCategoryViewSet
from .views import clickpesa_webhook

router = DefaultRouter()
router.register(r"appointments", AppointmentViewSet, basename="appointment")
router.register(
    r"illness_category", IllnessCategoryViewSet, basename="illness-category"
)

urlpatterns = [
    path("webhooks/payments/", clickpesa_webhook),
]

urlpatterns += router.urls
