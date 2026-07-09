from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include, re_path
from rest_framework.permissions import IsAdminUser
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    # admin panel endpoint
    path("admin/", admin.site.urls),
    # djoser endpoints
    re_path(r"^api/auth/", include("djoser.urls")),
    re_path(r"^api/auth/", include("djoser.urls.jwt")),
    # API DOCS ENDPOINTS
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema", ), name="swagger-ui"),
    # auth cookies based
    path("api/", include("api.accounts.urls")),
    # appointments
    path("api/", include("api.appointments.urls")),
    # consultations
    path("api/", include("api.consultations.urls")),
    # medical records
    path("api/", include("api.medical_records.urls")),
    # prescriptions
    path("api/", include("api.prescriptions.urls")),
    # laboratory
    path("api/", include("api.laboratory.urls")),
    # billing
    path("api/", include("api.billing.urls")),
    # pharmacy
    path("api/", include("api.pharmacy.urls")),
    # notifications
    path("api/", include("api.notifications.urls")),
    # health education
    path("api/", include("api.health_education.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
