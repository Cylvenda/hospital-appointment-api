from django.urls import path
from .views import (
    AdminDoctorsListView,
    AdminDoctorDetailView,
    AdminOverviewView,
    AdminSettingsView,
    AdminUserDetailView,
    AdminUsersListView,
    CustomeTokenObtainPairView,
    CustomeTokenVerifyView,
    CustomeTokenRefreshView,
    LogoutView,
    PublicSystemSettingsView,
    ReportGenerationView,
)

urlpatterns = [
    path("me/auth/login/", CustomeTokenObtainPairView.as_view(), name="login"),
    path("me/auth/token/refresh/", CustomeTokenRefreshView.as_view(), name="token_refresh"),
    path("me/auth/token/verify/", CustomeTokenVerifyView.as_view(), name="token_verify"),
    path("me/auth/logout/", LogoutView.as_view(), name="logout"),
    path("me/auth/csrf/", CustomeTokenRefreshView.as_view(), name="csrf"),
    path("public/settings/", PublicSystemSettingsView.as_view(), name="public-settings"),
    path("admin/overview/", AdminOverviewView.as_view(), name="admin-overview"),
    path("admin/users/", AdminUsersListView.as_view(), name="admin-users"),
    path("admin/users/<uuid:uuid>/", AdminUserDetailView.as_view(), name="admin-user-detail"),
    path("admin/doctors/", AdminDoctorsListView.as_view(), name="admin-doctors"),
    path(
        "admin/doctors/<uuid:uuid>/",
        AdminDoctorDetailView.as_view(),
        name="admin-doctor-detail",
    ),
    path("admin/settings/", AdminSettingsView.as_view(), name="admin-settings"),
    path("me/report/export/", ReportGenerationView.as_view(), name="me-report-export"),
]
