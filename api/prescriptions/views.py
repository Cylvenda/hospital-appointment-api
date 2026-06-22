from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from .models import Prescription, PrescriptionItem
from .serializers import (
    PrescriptionItemSerializer,
    PrescriptionItemWriteSerializer,
    PrescriptionSerializer,
    PrescriptionWriteSerializer,
)


class PrescriptionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, "role", None)
        queryset = Prescription.objects.select_related(
            "consultation__appointment",
            "doctor__user",
            "patient__user",
        ).prefetch_related("items")

        if role in {"admin", "receptionist"}:
            return queryset.order_by("-created_at")

        if role == "doctor":
            return queryset.filter(doctor__user=user).order_by("-created_at")

        if role == "patient":
            return queryset.filter(patient__user=user).order_by("-created_at")

        return Prescription.objects.none()

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return PrescriptionWriteSerializer
        return PrescriptionSerializer

    def perform_create(self, serializer):
        role = getattr(self.request.user, "role", None)
        if role not in {"admin", "receptionist", "doctor"}:
            raise PermissionDenied("You do not have permission to create prescriptions.")
        serializer.save()


class PrescriptionItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, "role", None)
        queryset = PrescriptionItem.objects.select_related(
            "prescription__consultation__appointment",
            "prescription__doctor__user",
            "prescription__patient__user",
        )

        if role in {"admin", "receptionist"}:
            return queryset.order_by("medicine_name")

        if role == "doctor":
            return queryset.filter(prescription__doctor__user=user).order_by("medicine_name")

        if role == "patient":
            return queryset.filter(prescription__patient__user=user).order_by("medicine_name")

        return PrescriptionItem.objects.none()

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return PrescriptionItemWriteSerializer
        return PrescriptionItemSerializer

    def perform_create(self, serializer):
        role = getattr(self.request.user, "role", None)
        if role not in {"admin", "receptionist", "doctor"}:
            raise PermissionDenied("You do not have permission to create prescription items.")
        serializer.save()

