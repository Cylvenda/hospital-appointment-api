from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from api.notifications.services import create_and_send_notification
from api.appointments.models import Appointment

from .models import LabRequest, LabRequestItem, LabResult, LabTestType
from .report_generator import generate_docx_report, generate_pdf_report
from .serializers import (
    LabRequestItemSerializer,
    LabRequestItemWriteSerializer,
    LabRequestSerializer,
    LabRequestWriteSerializer,
    LabResultSerializer,
    LabResultWriteSerializer,
    LabTestTypeSerializer,
)


class LabTestTypeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def get_queryset(self):
        return LabTestType.objects.order_by("name")

    def get_serializer_class(self):
        return LabTestTypeSerializer

    def perform_create(self, serializer):
        role = getattr(self.request.user, "role", None)
        if role not in {"admin", "receptionist", "doctor", "lab_tech"}:
            raise PermissionDenied("You do not have permission to create lab tests.")
        serializer.save()


class LabRequestViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, "role", None)
        queryset = LabRequest.objects.select_related(
            "consultation__appointment",
            "doctor__user",
            "patient__user",
        ).prefetch_related("items__test_type", "items__result")

        if role == "lab_tech":
            return queryset.exclude(status=LabRequest.Status.COMPLETED).order_by(
                "requested_at"
            )

        if role in {"admin", "receptionist"}:
            return queryset.order_by("-requested_at")

        if role == "doctor":
            return queryset.filter(doctor__user=user).order_by("-requested_at")

        if role == "patient":
            return queryset.filter(patient__user=user).order_by("-requested_at")

        return LabRequest.objects.none()

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return LabRequestWriteSerializer
        return LabRequestSerializer

    def perform_create(self, serializer):
        role = getattr(self.request.user, "role", None)
        if role not in {"admin", "receptionist", "doctor", "lab_tech"}:
            raise PermissionDenied("You do not have permission to create lab requests.")
        serializer.save()

    def perform_update(self, serializer):
        if getattr(self.request.user, "role", None) not in {
            "admin",
            "receptionist",
            "lab_tech",
        }:
            raise PermissionDenied("Only laboratory staff can update lab requests.")

        requested_status = serializer.validated_data.get(
            "status",
            serializer.instance.status,
        )
        if requested_status == LabRequest.Status.COMPLETED:
            if serializer.instance.items.exclude(result__isnull=False).exists():
                raise ValidationError(
                    {"status": "Every requested test requires a result before submission."}
                )

        lab_request = serializer.save()
        appointment = lab_request.consultation.appointment
        if requested_status in {
            LabRequest.Status.SAMPLE_COLLECTED,
            LabRequest.Status.PROCESSING,
        }:
            appointment.status = Appointment.Status.LABORATORY_IN_PROGRESS
            appointment.save(update_fields=["status", "updated_at"])
        elif requested_status == LabRequest.Status.COMPLETED:
            appointment.status = Appointment.Status.BACK_TO_DOCTOR
            appointment.save(update_fields=["status", "updated_at"])

            doctor_user = getattr(lab_request.doctor, "user", None)
            patient_user = getattr(lab_request.patient, "user", None)
            if doctor_user:
                create_and_send_notification(
                    user=doctor_user,
                    title="Laboratory Results Ready",
                    message="Laboratory results are ready for review.",
                    notification_type="lab_result_available",
                    appointment=appointment,
                    triggered_by=self.request.user,
                )
            if patient_user:
                create_and_send_notification(
                    user=patient_user,
                    title="Laboratory Tests Complete",
                    message="Your laboratory tests are complete. Please return to your doctor.",
                    notification_type="lab_result_available",
                    appointment=appointment,
                    triggered_by=self.request.user,
                )

    @action(detail=True, methods=["get"], url_path="export")
    def export_report(self, request, uuid=None):
        lab_request = self.get_object()
        format_type = request.query_params.get("format", "pdf").lower()
        
        if format_type == "docx":
            buffer = generate_docx_report(lab_request)
            response = HttpResponse(
                buffer, 
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            response["Content-Disposition"] = f'attachment; filename="lab_report_{lab_request.uuid}.docx"'
            return response
            
        elif format_type == "pdf":
            buffer = generate_pdf_report(lab_request)
            response = HttpResponse(buffer, content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="lab_report_{lab_request.uuid}.pdf"'
            return response
            
        else:
            raise ValidationError({"detail": "Invalid format type. Supported formats are 'pdf' and 'docx'."})


class LabRequestItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, "role", None)
        queryset = LabRequestItem.objects.select_related(
            "lab_request__consultation__appointment",
            "lab_request__doctor__user",
            "lab_request__patient__user",
            "test_type",
        )

        if role in {"admin", "receptionist", "lab_tech"}:
            return queryset.order_by("test_type__name")

        if role == "doctor":
            return queryset.filter(lab_request__doctor__user=user).order_by("test_type__name")

        if role == "patient":
            return queryset.filter(lab_request__patient__user=user).order_by("test_type__name")

        return LabRequestItem.objects.none()

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return LabRequestItemWriteSerializer
        return LabRequestItemSerializer

    def perform_create(self, serializer):
        role = getattr(self.request.user, "role", None)
        if role not in {"admin", "receptionist", "doctor", "lab_tech"}:
            raise PermissionDenied("You do not have permission to create lab request items.")
        serializer.save()


class LabResultViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, "role", None)
        queryset = LabResult.objects.select_related(
            "request_item__test_type",
            "request_item__lab_request__consultation__appointment",
            "request_item__lab_request__doctor__user",
            "request_item__lab_request__patient__user",
            "verified_by",
        )

        if role in {"admin", "receptionist", "lab_tech"}:
            return queryset.order_by("-created_at")

        if role == "doctor":
            return queryset.filter(request_item__lab_request__doctor__user=user).order_by("-created_at")

        if role == "patient":
            return queryset.filter(request_item__lab_request__patient__user=user).order_by("-created_at")

        return LabResult.objects.none()

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return LabResultWriteSerializer
        return LabResultSerializer

    def perform_create(self, serializer):
        role = getattr(self.request.user, "role", None)
        if role not in {"admin", "lab_tech"}:
            raise PermissionDenied("You do not have permission to create lab results.")
        result = serializer.save(
            verified_by=self.request.user,
            verified_at=timezone.now(),
        )

        patient_user = getattr(getattr(result.request_item.lab_request.patient, "user", None), "email", None)
        if result.request_item.lab_request.patient and result.request_item.lab_request.patient.user:
            create_and_send_notification(
                user=result.request_item.lab_request.patient.user,
                title="Lab Result Available",
                message="A lab result has been completed and is now available in your record.",
                notification_type="lab_result_available",
                triggered_by=self.request.user,
                extra_info=f"Test: {result.request_item.test_type.name}",
            )
