from django.urls import path
from .views import (
    AdminDoctorsListView,
    AdminOverviewView,
    AdminSettingsView,
    AdminUserDetailView,
    AdminUsersListView,
    CustomeTokenObtainPairView,
    CustomeTokenVerifyView,
    CustomeTokenRefreshView,
    LogoutView,
    RegionListView,
    DistrictListView,
)

urlpatterns = [
    path("me/auth/login/", CustomeTokenObtainPairView.as_view(), name="login"),
    path("me/auth/refresh/", CustomeTokenVerifyView.as_view(), name="token_refresh"),
    path("me/auth/logout/", LogoutView.as_view(), name="logout"),
    path("me/auth/csrf/", CustomeTokenRefreshView.as_view(), name="csrf"),
    path("admin/overview/", AdminOverviewView.as_view(), name="admin-overview"),
    path("admin/users/", AdminUsersListView.as_view(), name="admin-users"),
    path("admin/users/<uuid:uuid>/", AdminUserDetailView.as_view(), name="admin-user-detail"),
    path("admin/doctors/", AdminDoctorsListView.as_view(), name="admin-doctors"),
    path("admin/settings/", AdminSettingsView.as_view(), name="admin-settings"),
    path("regions/", RegionListView.as_view(), name="region-list"),
    path("districts/", DistrictListView.as_view(), name="district-list"),
]
