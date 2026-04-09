from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from rest_framework.views import APIView
from rest_framework.response import Response
from api.appointments.models import Appointment
from api.notifications.models import Notification
from .models import DoctorProfile, User
from .serializers import (
    AdminDoctorWriteSerializer,
    AdminOverviewSerializer,
    AdminSettingsSerializer,
    AdminUserSerializer,
    AdminUserWriteSerializer,
    DoctorDirectorySerializer,
)


class IsAdminOrReceptionist(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in [User.Role.ADMIN, User.Role.RECEPTIONIST]
        )


class CustomeTokenObtainPairView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            access_token = response.data.get("access")
            refresh_token = response.data.get("refresh")

            response.set_cookie(
                key="access",
                value=access_token,
                max_age=settings.AUTH_COOKIE_ACCESS_MAX_AGE,
                path=settings.AUTH_COOKIE_PATH,
                secure=settings.AUTH_COOKIE_SECURE,
                httponly=settings.AUTH_COOKIE_HTTP_ONLY,
                samesite=settings.AUTH_COOKIE_SAMESITE,
            )
            response.set_cookie(
                key="refresh",
                value=refresh_token,
                max_age=settings.AUTH_COOKIE_REFRESH_MAX_AGE,
                path=settings.AUTH_COOKIE_PATH,
                secure=settings.AUTH_COOKIE_SECURE,
                httponly=settings.AUTH_COOKIE_HTTP_ONLY,
                samesite=settings.AUTH_COOKIE_SAMESITE,
            )

        return response


class CustomeTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get("refresh")

        if refresh_token:
            data = request.data.copy()
            data["refresh"] = refresh_token
            request._full_data = data

        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            access_token = response.data.get("access")

            response.set_cookie(
                key="access",
                value=access_token,
                max_age=settings.AUTH_COOKIE_ACCESS_MAX_AGE,
                path=settings.AUTH_COOKIE_PATH,
                secure=settings.AUTH_COOKIE_SECURE,
                httponly=settings.AUTH_COOKIE_HTTP_ONLY,
                samesite=settings.AUTH_COOKIE_SAMESITE,
            )

        return response


class CustomeTokenVerifyView(TokenVerifyView):
    def post(self, request, *args, **kwargs):
        access_token = request.COOKIES.get("access")

        if access_token:
            data = request.data.copy()
            data["token"] = access_token
            request._full_data = data

        return super().post(request, *args, **kwargs)


class LogoutView(APIView):
    def post(self, request, *args, **kwargs):
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.delete_cookie("access", path=settings.AUTH_COOKIE_PATH)
        response.delete_cookie("refresh", path=settings.AUTH_COOKIE_PATH)
        return response


class AdminOverviewView(GenericAPIView):
    serializer_class = AdminOverviewSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrReceptionist]

    def get(self, request, *args, **kwargs):
        today = timezone.localdate()
        payload = {
            "total_users": User.objects.count(),
            "total_patients": User.objects.filter(role=User.Role.PATIENT).count(),
            "total_doctors": DoctorProfile.objects.count(),
            "total_receptionists": User.objects.filter(
                role=User.Role.RECEPTIONIST
            ).count(),
            "active_users": User.objects.filter(is_active=True).count(),
            "today_appointments": Appointment.objects.filter(
                appointment_date=today
            ).count(),
            "pending_appointments": Appointment.objects.filter(
                status=Appointment.Status.PENDING
            ).count(),
            "approved_appointments": Appointment.objects.filter(
                status=Appointment.Status.ACCEPTED
            ).count(),
            "cancelled_appointments": Appointment.objects.filter(
                status=Appointment.Status.CANCELLED
            ).count(),
            "unread_notifications": Notification.objects.filter(
                user=request.user, is_read=False
            ).count(),
        }
        serializer = self.get_serializer(payload)
        return Response(serializer.data)


class AdminUsersListView(ListAPIView):
    serializer_class = AdminUserSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrReceptionist]

    def get_queryset(self):
        queryset = User.objects.all().order_by("first_name", "last_name", "email")
        role = self.request.query_params.get("role")
        if role:
            queryset = queryset.filter(role=role)
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(phone__icontains=search)
            )
        return queryset

    def post(self, request, *args, **kwargs):
        serializer = AdminUserWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(AdminUserSerializer(user).data, status=status.HTTP_201_CREATED)


class AdminUserDetailView(GenericAPIView):
    serializer_class = AdminUserWriteSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrReceptionist]

    def get_object(self, uuid):
        return get_object_or_404(User, uuid=uuid)

    def patch(self, request, uuid, *args, **kwargs):
        user = self.get_object(uuid)
        serializer = self.get_serializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AdminUserSerializer(user).data, status=status.HTTP_200_OK)

    def delete(self, request, uuid, *args, **kwargs):
        user = self.get_object(uuid)
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminDoctorsListView(ListAPIView):
    serializer_class = DoctorDirectorySerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrReceptionist]

    def get_queryset(self):
        queryset = DoctorProfile.objects.select_related("user").prefetch_related(
            "doctorcategory_set__category"
        )
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(user__email__icontains=search)
                | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
            )
        return queryset.order_by("user__first_name", "user__last_name")

    def post(self, request, *args, **kwargs):
        serializer = AdminDoctorWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        doctor = serializer.save()
        return Response(DoctorDirectorySerializer(doctor).data, status=status.HTTP_201_CREATED)


class AdminSettingsView(GenericAPIView):
    serializer_class = AdminSettingsSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrReceptionist]

    def get(self, request, *args, **kwargs):
        payload = {
            "clinic_name": getattr(settings, "SITE_NAME", "Meeting Hub"),
            "support_email": getattr(settings, "DEFAULT_FROM_EMAIL", "support@localhost"),
            "clinic_hours": "07:30 AM - 06:00 PM",
            "default_time_slot": "30 minutes",
            "secure_sessions": True,
            "patient_confirmation_emails": bool(getattr(settings, "EMAIL_HOST", "")),
        }
        serializer = self.get_serializer(payload)
        return Response(serializer.data)
