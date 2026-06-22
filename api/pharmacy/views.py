from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from api.notifications.services import create_and_send_notification

from .models import Dispensing, DispensingItem, Medicine
from .serializers import (
    DispensingItemSerializer,
    DispensingItemWriteSerializer,
    DispensingSerializer,
    DispensingWriteSerializer,
    MedicineSerializer,
)


ALLOWED_CLINICAL_ROLES = {"admin", "receptionist", "doctor"}


class MedicineViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def get_queryset(self):
        return Medicine.objects.order_by("name")

    def get_serializer_class(self):
        return MedicineSerializer

    def perform_create(self, serializer):
        role = getattr(self.request.user, "role", None)
        if role not in ALLOWED_CLINICAL_ROLES:
            raise PermissionDenied("You do not have permission to create medicines.")
        serializer.save()


class DispensingViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, "role", None)
        queryset = Dispensing.objects.select_related(
            "prescription__patient__user",
            "prescription__consultation__appointment",
            "pharmacist",
        ).prefetch_related("items__medicine")

        if role in {"admin", "receptionist"}:
            return queryset.order_by("-created_at")

        if role == "doctor":
            return queryset.filter(prescription__doctor__user=user).order_by("-created_at")

        if role == "patient":
            return queryset.filter(prescription__patient__user=user).order_by("-created_at")

        return Dispensing.objects.none()

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return DispensingWriteSerializer
        return DispensingSerializer

    def _ensure_editable(self, dispensing):
        if dispensing.status != Dispensing.Status.PENDING:
            raise ValidationError(
                {"status": "Only pending dispensings can be modified."}
            )

    def _ensure_inventory(self, dispensing):
        shortages = []
        for item in dispensing.items.select_related("medicine").all():
            medicine = item.medicine
            if medicine.stock_quantity < item.quantity:
                shortages.append(
                    {
                        "medicine_uuid": str(medicine.uuid),
                        "medicine_name": medicine.name,
                        "available": medicine.stock_quantity,
                        "required": item.quantity,
                    }
                )

        if shortages:
            raise ValidationError(
                {"stock": "Not enough stock to dispense all requested medicines.", "shortages": shortages}
            )

    def _consume_stock(self, dispensing):
        self._ensure_inventory(dispensing)
        for item in dispensing.items.select_related("medicine").all():
            medicine = item.medicine
            medicine.stock_quantity -= item.quantity
            medicine.save(update_fields=["stock_quantity", "updated_at"])

    def perform_create(self, serializer):
        role = getattr(self.request.user, "role", None)
        if role not in ALLOWED_CLINICAL_ROLES:
            raise PermissionDenied("You do not have permission to create dispensings.")
        prescription = serializer.validated_data.get("prescription")
        if prescription and getattr(prescription, "dispensing", None):
            raise ValidationError({"prescription_uuid": "This prescription has already been dispensed."})

        with transaction.atomic():
            dispensing = serializer.save()
            if not dispensing.pharmacist:
                dispensing.pharmacist = self.request.user
            if dispensing.status == Dispensing.Status.DISPENSED:
                self._consume_stock(dispensing)
                dispensing.dispensed_at = dispensing.dispensed_at or timezone.now()
            dispensing.save(update_fields=["pharmacist", "dispensed_at", "status", "updated_at"])

        if dispensing.status == Dispensing.Status.DISPENSED:
            patient = getattr(getattr(dispensing.prescription, "patient", None), "user", None)
            if patient:
                create_and_send_notification(
                    user=patient,
                    title="Prescription Ready",
                    message="Your prescription has been dispensed and is ready for collection.",
                    notification_type="dispensing_ready",
                    triggered_by=self.request.user,
                    extra_info=f"Prescription: {dispensing.prescription.uuid}",
                )

    def perform_update(self, serializer):
        role = getattr(self.request.user, "role", None)
        if role not in ALLOWED_CLINICAL_ROLES:
            raise PermissionDenied("You do not have permission to update dispensings.")

        dispensing = self.get_object()
        previous_status = dispensing.status

        with transaction.atomic():
            self._ensure_editable(dispensing)
            updated = serializer.save()

            if updated.status == Dispensing.Status.DISPENSED:
                self._consume_stock(updated)
                updated.pharmacist = updated.pharmacist or self.request.user
                updated.dispensed_at = updated.dispensed_at or timezone.now()
                updated.save(update_fields=["pharmacist", "dispensed_at", "status", "updated_at"])

        if previous_status != updated.status and updated.status == Dispensing.Status.DISPENSED:
            patient = getattr(getattr(updated.prescription, "patient", None), "user", None)
            if patient:
                create_and_send_notification(
                    user=patient,
                    title="Prescription Ready",
                    message="Your prescription has been dispensed and is ready for collection.",
                    notification_type="dispensing_ready",
                    triggered_by=self.request.user,
                    extra_info=f"Prescription: {updated.prescription.uuid}",
                )


class DispensingItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, "role", None)
        queryset = DispensingItem.objects.select_related(
            "dispensing__prescription__patient__user",
            "dispensing__prescription__doctor__user",
            "medicine",
        )

        if role in {"admin", "receptionist"}:
            return queryset.order_by("-created_at")

        if role == "doctor":
            return queryset.filter(dispensing__prescription__doctor__user=user).order_by("-created_at")

        if role == "patient":
            return queryset.filter(dispensing__prescription__patient__user=user).order_by("-created_at")

        return DispensingItem.objects.none()

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return DispensingItemWriteSerializer
        return DispensingItemSerializer

    def _ensure_editable(self, dispensing):
        if dispensing.status != Dispensing.Status.PENDING:
            raise ValidationError(
                {"dispensing_uuid": "Dispensing items can only be modified while the dispensing is pending."}
            )

    def perform_create(self, serializer):
        role = getattr(self.request.user, "role", None)
        if role not in ALLOWED_CLINICAL_ROLES:
            raise PermissionDenied("You do not have permission to create dispensing items.")
        dispensing = serializer.validated_data.get("dispensing")
        if dispensing:
            self._ensure_editable(dispensing)
        serializer.save()

    def perform_update(self, serializer):
        role = getattr(self.request.user, "role", None)
        if role not in ALLOWED_CLINICAL_ROLES:
            raise PermissionDenied("You do not have permission to update dispensing items.")
        dispensing = getattr(serializer.instance, "dispensing", None)
        if dispensing:
            self._ensure_editable(dispensing)
        serializer.save()

    def perform_destroy(self, instance):
        role = getattr(self.request.user, "role", None)
        if role not in ALLOWED_CLINICAL_ROLES:
            raise PermissionDenied("You do not have permission to delete dispensing items.")
        if instance.dispensing:
            self._ensure_editable(instance.dispensing)
        instance.delete()
