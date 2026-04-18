from django.contrib import admin
from django.urls import path, include, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    # admin panel endpoint
    path("admin/", admin.site.urls),
    # djoser endpoints
    re_path(r"^api/auth/", include("djoser.urls")),
    re_path(r"^api/auth/", include("djoser.urls.jwt")),
    # API DOCS ENDPOINTS
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    # auth cookies based
    path("api/", include("api.accounts.urls")),
    # appointments
    path("api/", include("api.appointments.urls")),
    # notifications
    path("api/", include("api.notifications.urls")),
]
