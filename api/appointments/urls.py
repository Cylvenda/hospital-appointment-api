from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    AppointmentViewSet,
    DoctorScheduleViewSet,
    DoctorUnavailableDateViewSet,
    IllnessCategoryViewSet,
)
from .views import clickpesa_webhook

router = DefaultRouter()
router.register(r"appointments", AppointmentViewSet, basename="appointment")
router.register(
    r"illness_category", IllnessCategoryViewSet, basename="illness-category"
)
router.register(r"doctor-schedules", DoctorScheduleViewSet, basename="doctor-schedule")
router.register(
    r"doctor-unavailable-dates",
    DoctorUnavailableDateViewSet,
    basename="doctor-unavailable-date",
)

urlpatterns = [
    path("webhooks/payments/", clickpesa_webhook),
]

urlpatterns += router.urls
