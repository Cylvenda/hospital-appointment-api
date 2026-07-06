from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied

from .models import Consultation
from .serializers import (
    ConsultationSerializer,
    ConsultationWriteSerializer,
    DiagnosisCreateSerializer,
    PrescriptionCreateSerializer,
    LabRequestCreateSerializer,
    InvoiceCreateSerializer,
)
from api.notifications.services import create_and_send_notification
from api.medical_records.models import Diagnosis
from api.prescriptions.models import Prescription, PrescriptionItem
from api.laboratory.models import LabRequest, LabRequestItem
from api.billing.models import Invoice, InvoiceItem
from .report_generator import generate_encounter_docx, generate_encounter_pdf


class ConsultationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, "role", None)

        queryset = Consultation.objects.select_related(
            "appointment",
            "doctor__user",
            "patient__user",
        )

        if role in {"admin", "receptionist"}:
            return queryset.order_by("-started_at")

        if role == "doctor":
            return queryset.filter(doctor__user=user).order_by("-started_at")

        if role == "patient":
            return queryset.filter(patient__user=user).order_by("-started_at")

        return Consultation.objects.none()

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return ConsultationWriteSerializer
        return ConsultationSerializer

    def perform_create(self, serializer):
        role = getattr(self.request.user, "role", None)
        if role not in {"admin", "receptionist", "doctor"}:
            raise PermissionDenied("You do not have permission to create consultations.")
        serializer.save()

    def _notify_patient(self, consultation, title, message, notification_type, extra_info=None):
        patient = self._resolve_patient(consultation)
        patient_user = getattr(patient, "user", None)
        if not patient_user:
            return

        create_and_send_notification(
            user=patient_user,
            title=title,
            message=message,
            notification_type=notification_type,
            appointment=consultation.appointment,
            triggered_by=self.request.user,
            extra_info=extra_info,
            send_email=True,
        )

    def _resolve_patient(self, consultation):
        if consultation.patient:
            return consultation.patient
        appointment_user = getattr(consultation.appointment, "created_by", None)
        return getattr(appointment_user, "patient_profile", None)

    def _resolve_doctor(self, consultation):
        if consultation.doctor:
            return consultation.doctor
        return getattr(consultation.appointment, "doctor", None)

    def _ensure_clinician_role(self):
        if getattr(self.request.user, "role", None) not in {"admin", "receptionist", "doctor"}:
            raise PermissionDenied("You do not have permission to perform this consultation action.")

    def _ensure_assigned_doctor(self, consultation):
        role = getattr(self.request.user, "role", None)
        if role == "admin":
            return
        doctor = self._resolve_doctor(consultation)
        if role != "doctor" or not doctor or doctor.user != self.request.user:
            raise PermissionDenied("Only the assigned doctor can perform this action.")

    @action(detail=True, methods=["post"])
    def start(self, request, uuid=None):
        self._ensure_clinician_role()
        consultation = self.get_object()
        self._ensure_assigned_doctor(consultation)

        if consultation.status != Consultation.Status.IN_PROGRESS:
            consultation.status = Consultation.Status.IN_PROGRESS
            consultation.save(update_fields=["status", "updated_at"])

        appointment = consultation.appointment
        if appointment.status in {
            appointment.Status.WAITING_IN_QUEUE,
            appointment.Status.BACK_TO_DOCTOR,
        }:
            appointment.status = appointment.Status.IN_CONSULTATION
            appointment.save(update_fields=["status", "updated_at"])

        self._notify_patient(
            consultation,
            title="Consultation Started",
            message="Your consultation has started and the clinical team is now reviewing your case.",
            notification_type="consultation_started",
        )

        return Response({"detail": "Consultation marked as in progress."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def complete(self, request, uuid=None):
        self._ensure_clinician_role()
        consultation = self.get_object()
        self._ensure_assigned_doctor(consultation)

        if consultation.lab_requests.exclude(
            status=LabRequest.Status.COMPLETED
        ).exists():
            raise ValidationError(
                {"detail": "Consultation cannot be completed while laboratory work is pending."}
            )

        consultation.status = Consultation.Status.COMPLETED
        consultation.completed_at = consultation.completed_at or timezone.now()
        consultation.save(update_fields=["status", "completed_at", "updated_at"])

        if consultation.appointment and consultation.appointment.status != consultation.appointment.Status.COMPLETED:
            consultation.appointment.status = consultation.appointment.Status.COMPLETED
            consultation.appointment.save(update_fields=["status", "updated_at"])

        self._notify_patient(
            consultation,
            title="Consultation Completed",
            message="Your consultation has been completed. You can now view any diagnoses, prescriptions, invoices, or lab results linked to it.",
            notification_type="consultation_completed",
        )

        return Response({"detail": "Consultation completed."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="export")
    def export_record(self, request, uuid=None):
        consultation = self.get_object()
        format_type = request.query_params.get("file_format", "pdf").lower()

        if format_type == "pdf":
            buffer = generate_encounter_pdf(consultation)
            response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
            extension = "pdf"
        elif format_type == "docx":
            buffer = generate_encounter_docx(consultation)
            response = HttpResponse(
                buffer.getvalue(),
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
            extension = "docx"
        else:
            raise ValidationError(
                {"detail": "Invalid format. Supported formats are 'pdf' and 'docx'."}
            )

        response["Content-Disposition"] = (
            f'attachment; filename="clinical_record_{consultation.appointment.uuid}.{extension}"'
        )
        return response

    @action(detail=True, methods=["post"], url_path="diagnoses")
    def add_diagnosis(self, request, uuid=None):
        self._ensure_clinician_role()
        consultation = self.get_object()
        serializer = DiagnosisCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        diagnosis = Diagnosis.objects.create(
            consultation=consultation,
            **serializer.validated_data,
        )

        if diagnosis.type == Diagnosis.DiagnosisType.PROVISIONAL and consultation.provisional_diagnosis != diagnosis.disease_name:
            consultation.provisional_diagnosis = diagnosis.disease_name
            consultation.save(update_fields=["provisional_diagnosis", "updated_at"])

        self._notify_patient(
            consultation,
            title="Diagnosis Added",
            message=f"A new {diagnosis.get_type_display().lower()} diagnosis has been added to your consultation.",
            notification_type="diagnosis_added",
            extra_info=f"{diagnosis.disease_name} {diagnosis.icd10_code or ''}".strip(),
        )

        return Response(
            {
                "detail": "Diagnosis added successfully.",
                "diagnosis_uuid": diagnosis.uuid,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="prescriptions")
    def create_prescription(self, request, uuid=None):
        self._ensure_clinician_role()
        consultation = self.get_object()
        serializer = PrescriptionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            patient = self._resolve_patient(consultation)
            if not patient:
                raise ValidationError({"patient": "A patient profile is required to create a prescription."})
            prescription = Prescription.objects.create(
                consultation=consultation,
                doctor=self._resolve_doctor(consultation),
                patient=patient,
                notes=serializer.validated_data.get("notes", ""),
            )
            for item_data in serializer.validated_data.get("items", []):
                PrescriptionItem.objects.create(
                    prescription=prescription,
                    **item_data,
                )

        self._notify_patient(
            consultation,
            title="Prescription Ready",
            message="A prescription has been added to your consultation and is now available for review.",
            notification_type="prescription_ready",
        )

        return Response(
            {
                "detail": "Prescription created successfully.",
                "prescription_uuid": prescription.uuid,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="lab-requests")
    def create_lab_request(self, request, uuid=None):
        self._ensure_clinician_role()
        consultation = self.get_object()
        self._ensure_assigned_doctor(consultation)
        serializer = LabRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            patient = self._resolve_patient(consultation)
            if not patient:
                raise ValidationError({"patient": "A patient profile is required to create a lab request."})
            lab_request = LabRequest.objects.create(
                consultation=consultation,
                doctor=self._resolve_doctor(consultation),
                patient=patient,
                status=serializer.validated_data.get("status", LabRequest.Status.PENDING),
                notes=serializer.validated_data.get("notes", ""),
            )
            for item_data in serializer.validated_data.get("items", []):
                LabRequestItem.objects.create(
                    lab_request=lab_request,
                    **item_data,
                )

            consultation.appointment.status = (
                consultation.appointment.Status.WAITING_FOR_LABORATORY
            )
            consultation.appointment.save(update_fields=["status", "updated_at"])

        self._notify_patient(
            consultation,
            title="Lab Test Requested",
            message="Your consultation now has one or more lab tests attached to it.",
            notification_type="lab_requested",
        )

        return Response(
            {
                "detail": "Lab request created successfully.",
                "lab_request_uuid": lab_request.uuid,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="invoices")
    def create_invoice(self, request, uuid=None):
        if getattr(self.request.user, "role", None) not in {"admin", "receptionist"}:
            raise PermissionDenied("You do not have permission to issue invoices.")
        consultation = self.get_object()
        serializer = InvoiceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            patient = self._resolve_patient(consultation)
            if not patient:
                raise ValidationError({"patient": "A patient profile is required to create an invoice."})
            invoice = Invoice.objects.create(
                patient=patient,
                consultation=consultation,
                status=serializer.validated_data.get("status", Invoice.Status.UNPAID),
            )
            items = serializer.validated_data.get("items", [])
            if not items:
                items = [
                    {
                        "item_type": InvoiceItem.ItemType.CONSULTATION,
                        "description": consultation.appointment.category.name if consultation.appointment and consultation.appointment.category else "Consultation Fee",
                        "quantity": 1,
                        "unit_price": consultation.appointment.fee if consultation.appointment else 0,
                    }
                ]

            for item_data in items:
                InvoiceItem.objects.create(invoice=invoice, **item_data)

        self._notify_patient(
            consultation,
            title="Invoice Issued",
            message="An invoice has been created for your consultation.",
            notification_type="invoice_issued",
            extra_info=f"Invoice #{invoice.invoice_number}",
        )

        return Response(
            {
                "detail": "Invoice created successfully.",
                "invoice_uuid": invoice.uuid,
            },
            status=status.HTTP_201_CREATED,
        )
