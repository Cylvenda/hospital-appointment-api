from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from .models import Diagnosis, PatientMedicalRecord
from .serializers import (
    DiagnosisSerializer,
    DiagnosisWriteSerializer,
    PatientMedicalRecordSerializer,
    PatientMedicalRecordWriteSerializer,
)


class PatientMedicalRecordViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, "role", None)
        queryset = PatientMedicalRecord.objects.select_related("patient__user")

        if role in {"admin", "receptionist", "doctor"}:
            return queryset.order_by("patient__user__last_name", "patient__user__first_name")

        if role == "patient":
            return queryset.filter(patient__user=user)

        return PatientMedicalRecord.objects.none()

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return PatientMedicalRecordWriteSerializer
        return PatientMedicalRecordSerializer

    def perform_create(self, serializer):
        role = getattr(self.request.user, "role", None)
        if role not in {"admin", "receptionist", "doctor"}:
            raise PermissionDenied("You do not have permission to create medical records.")
        serializer.save()


class DiagnosisViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, "role", None)
        queryset = Diagnosis.objects.select_related(
            "consultation__appointment",
            "consultation__doctor__user",
            "consultation__patient__user",
        )

        if role in {"admin", "receptionist"}:
            return queryset.order_by("-diagnosed_at")

        if role == "doctor":
            return queryset.filter(consultation__doctor__user=user).order_by("-diagnosed_at")

        if role == "patient":
            return queryset.filter(consultation__patient__user=user).order_by("-diagnosed_at")

        return Diagnosis.objects.none()

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return DiagnosisWriteSerializer
        return DiagnosisSerializer

    def perform_create(self, serializer):
        role = getattr(self.request.user, "role", None)
        if role not in {"admin", "receptionist", "doctor"}:
            raise PermissionDenied("You do not have permission to create diagnoses.")
        serializer.save()

