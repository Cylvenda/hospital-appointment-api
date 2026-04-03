from django.urls import path
from .views import (
    CustomeTokenObtainPairView,
    CustomeTokenVerifyView,
    CustomeTokenRefreshView,
    LogoutView,
)

urlpatterns = [
    path("me/auth/login/", CustomeTokenObtainPairView.as_view(), name="login"),
    path("me/auth/refresh/", CustomeTokenVerifyView.as_view(), name="token_refresh"),
    path("me/auth/logout/", LogoutView.as_view(), name="logout"),
    path("me/auth/csrf/", CustomeTokenRefreshView.as_view(), name="csrf"),
]
