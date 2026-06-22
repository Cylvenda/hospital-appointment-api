from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from .models import Invoice, InvoiceItem
from .serializers import (
    InvoiceItemSerializer,
    InvoiceItemWriteSerializer,
    InvoiceSerializer,
    InvoiceWriteSerializer,
)


class InvoiceViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, "role", None)
        queryset = Invoice.objects.select_related(
            "patient__user",
            "consultation__appointment",
        ).prefetch_related("items")

        if role in {"admin", "receptionist"}:
            return queryset.order_by("-issued_at")

        if role == "patient":
            return queryset.filter(patient__user=user).order_by("-issued_at")

        return Invoice.objects.none()

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return InvoiceWriteSerializer
        return InvoiceSerializer

    def perform_create(self, serializer):
        role = getattr(self.request.user, "role", None)
        if role not in {"admin", "receptionist"}:
            raise PermissionDenied("You do not have permission to create invoices.")
        serializer.save()


class InvoiceItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, "role", None)
        queryset = InvoiceItem.objects.select_related(
            "invoice__patient__user",
            "invoice__consultation__appointment",
        )

        if role in {"admin", "receptionist"}:
            return queryset.order_by("-created_at")

        if role == "patient":
            return queryset.filter(invoice__patient__user=user).order_by("-created_at")

        return InvoiceItem.objects.none()

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return InvoiceItemWriteSerializer
        return InvoiceItemSerializer

    def perform_create(self, serializer):
        role = getattr(self.request.user, "role", None)
        if role not in {"admin", "receptionist"}:
            raise PermissionDenied("You do not have permission to create invoice items.")
        serializer.save()
