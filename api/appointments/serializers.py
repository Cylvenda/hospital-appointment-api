from datetime import time

from django.db import IntegrityError, transaction
from rest_framework import serializers
from api.accounts.models import (
    DoctorAvailability,
    DoctorProfile,
    DoctorUnavailableDate,
)
from api.accounts.models import SystemSettings
from api.appointments.models import (
    IllnessCategory,
    Appointment,
    AppointmentLog,
    Payment,
    AppointmentQueue,
)
from .scheduling import validate_slot


class IllnessCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = IllnessCategory
        fields = ["uuid", "name", "description"]


class AppointmentSerializer(serializers.ModelSerializer):
    patient_uuid = serializers.UUIDField(source="created_by.uuid", read_only=True)
    patient_name = serializers.CharField(source="created_by.full_name", read_only=True)
    patient_email = serializers.EmailField(source="created_by.email", read_only=True)
    patient_phone = serializers.CharField(source="created_by.phone", read_only=True)
    patient_profile = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    doctor_uuid = serializers.UUIDField(source="doctor.uuid", read_only=True)
    payment_status = serializers.CharField(source="payment.status", read_only=True)
    illness_category = serializers.CharField(source="category.name", read_only=True)
    illness_category_uuid = serializers.UUIDField(
        source="category.uuid", read_only=True
    )
    queue_number = serializers.SerializerMethodField()
    checked_in_at = serializers.SerializerMethodField()

    def get_doctor_name(self, obj):
        if not obj.doctor:
            return None
        return obj.doctor.user.full_name or str(obj.doctor)

    def get_queue_number(self, obj):
        queue_entry = getattr(obj, "queue_entry", None)
        return queue_entry.queue_number if queue_entry else None

    def get_checked_in_at(self, obj):
        queue_entry = getattr(obj, "queue_entry", None)
        return queue_entry.checked_in_at if queue_entry else None

    def get_patient_profile(self, obj):
        profile = getattr(obj.created_by, "patient_profile", None)
        if not profile:
            return None
        next_of_kin = getattr(profile, "next_of_kin", None)
        return {
            "uuid": profile.uuid,
            "patient_id": profile.patient_id,
            "dob": profile.dob,
            "gender": profile.gender,
            "region": profile.region,
            "district": profile.district,
            "ward": profile.ward,
            "residence": profile.residence,
            "blood_group": profile.blood_group,
            "insurance_provider": profile.insurance_provider,
            "insurance_number": profile.insurance_number,
            "is_profile_complete": profile.is_profile_complete,
            "next_of_kin": (
                {
                    "name": next_of_kin.name,
                    "phone": next_of_kin.phone,
                    "relationship": next_of_kin.relationship,
                }
                if next_of_kin
                else None
            ),
        }

    class Meta:
        model = Appointment
        fields = [
            "uuid",
            "appointment_id",
            "patient_uuid",
            "patient_name",
            "patient_email",
            "patient_phone",
            "patient_profile",
            "doctor_name",
            "doctor_uuid",
            "payment_status",
            "fee",
            "illness_category",
            "illness_category_uuid",
            "description",
            "appointment_date",
            "start_time",
            "end_time",
            "status",
            "queue_number",
            "checked_in_at",
            "diagnosis",
            "notes",
            "created_at",
        ]


class AppointmentCreateSerializer(serializers.ModelSerializer):
    illness_category_uuid = serializers.SlugRelatedField(
        source="category", slug_field="uuid", queryset=IllnessCategory.objects.all()
    )
    doctor_uuid = serializers.SlugRelatedField(
        source="doctor",
        slug_field="uuid",
        queryset=DoctorProfile.objects.select_related("user").all(),
        required=False,
    )

    class Meta:
        model = Appointment
        fields = [
            "illness_category_uuid",
            "doctor_uuid",
            "appointment_date",
            "start_time",
            "description",
        ]
        validators = []

    def validate(self, attrs):
        doctor = attrs.get("doctor")
        appointment_date = attrs.get("appointment_date")
        start_time = attrs.get("start_time")
        schedule_values = (doctor, appointment_date, start_time)

        if any(schedule_values) and not all(schedule_values):
            raise serializers.ValidationError(
                "Doctor, appointment date, and start time must be selected together."
            )

        if doctor:
            category = attrs["category"]
            if not doctor.doctorcategory_set.filter(category=category).exists():
                raise serializers.ValidationError(
                    {"doctor_uuid": "This doctor is not assigned to the selected department."}
                )
            selected = validate_slot(doctor, appointment_date, start_time)
            attrs["end_time"] = time.fromisoformat(selected["end_time"])
            attrs["preferred_date"] = appointment_date

        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        clinic_settings = SystemSettings.get_solo()

        try:
            with transaction.atomic():
                return Appointment.objects.create(
                    created_by=user,
                    status=Appointment.Status.PENDING,
                    fee=clinic_settings.appointment_fee,
                    **validated_data,
                )
        except IntegrityError as error:
            raise serializers.ValidationError(
                {"start_time": "This slot was booked by another patient."}
            ) from error

    def to_representation(self, instance):
        return AppointmentSerializer(instance, context=self.context).data


class AppointmentPatientUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = [
            "description",
        ]

    def validate(self, attrs):
        legacy_fields = [
            "preferred_date",
            "preferred_date_2",
            "preferred_date_3",
        ]
        submitted = getattr(self, "initial_data", {})
        errors = {
            field: "This field is no longer supported for patient updates."
            for field in legacy_fields
            if field in submitted
        }
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def to_representation(self, instance):
        from api.appointments.serializers import AppointmentSerializer
        return AppointmentSerializer(instance, context=self.context).data


class AppointmentAssignSerializer(serializers.ModelSerializer):
    doctor_uuid = serializers.SlugRelatedField(
        source="doctor",
        slug_field="uuid",
        queryset=DoctorProfile.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Appointment
        fields = [
            "doctor_uuid",
            "appointment_date",
            "start_time",
            "end_time",
            "status",
        ]

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        status = attrs.get("status", getattr(instance, "status", None))

        if status and status not in [
            Appointment.Status.CONFIRMED,
            Appointment.Status.CANCELLED,
            Appointment.Status.NO_SHOW,
            Appointment.Status.RESCHEDULED,
        ]:
            raise serializers.ValidationError(
                "Receptionists and admins can only assign, cancel, or decline an appointment."
            )

        if status == Appointment.Status.CONFIRMED:
            missing_fields = {
                field: "This field is required when assigning an appointment."
                for field, source in [
                    ("doctor_uuid", "doctor"),
                    ("appointment_date", "appointment_date"),
                    ("start_time", "start_time"),
                    ("end_time", "end_time"),
                ]
                if not attrs.get(source) and not getattr(instance, source, None)
            }
            if missing_fields:
                raise serializers.ValidationError(missing_fields)

            doctor = attrs.get("doctor", instance.doctor)
            appointment_date = attrs.get(
                "appointment_date",
                instance.appointment_date,
            )
            start_time = attrs.get("start_time", instance.start_time)
            slot_changed = (
                doctor != instance.doctor
                or appointment_date != instance.appointment_date
                or start_time != instance.start_time
            )
            if slot_changed:
                selected = validate_slot(doctor, appointment_date, start_time)
                attrs["end_time"] = time.fromisoformat(selected["end_time"])

        return attrs

    def to_representation(self, instance):
        from api.appointments.serializers import AppointmentSerializer
        return AppointmentSerializer(instance, context=self.context).data


class AppointmentDoctorUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = ["diagnosis", "notes", "status"]

    def validate_status(self, value):
        if value not in [
            Appointment.Status.COMPLETED,
            Appointment.Status.CANCELLED,
            Appointment.Status.IN_CONSULTATION,
            Appointment.Status.WAITING_FOR_LABORATORY,
        ]:
            raise serializers.ValidationError(
                "Doctor cannot move the appointment to that workflow status."
            )
        return value

    def validate(self, attrs):
        next_status = attrs.get("status")
        if next_status == Appointment.Status.COMPLETED:
            if self.instance.status != Appointment.Status.IN_CONSULTATION:
                raise serializers.ValidationError(
                    {"status": "Start the consultation before completing it."}
                )
            consultation = getattr(self.instance, "consultation", None)
            if consultation and consultation.lab_requests.exclude(
                status="completed"
            ).exists():
                raise serializers.ValidationError(
                    {"status": "Laboratory work must be completed before this consultation."}
                )
        return attrs

    def to_representation(self, instance):
        from api.appointments.serializers import AppointmentSerializer
        return AppointmentSerializer(instance, context=self.context).data


class AppointmentLogSerializer(serializers.ModelSerializer):
    performed_by = serializers.StringRelatedField()

    class Meta:
        model = AppointmentLog
        fields = [
            "id",
            "appointment",
            "action",
            "performed_by",
            "timestamp",
        ]
        



class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "uuid",
            "appointment",
            "amount",
            "status",
            "payment_method",
            "transaction_reference",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "uuid",
            "created_at",
            "updated_at",
            "status",
            "transaction_reference",
        ]


class DoctorOptionSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="user.full_name", read_only=True)
    department_uuids = serializers.SerializerMethodField()

    class Meta:
        model = DoctorProfile
        fields = [
            "uuid",
            "name",
            "is_available",
            "consultation_duration",
            "max_appointments_per_day",
            "department_uuids",
        ]

    def get_department_uuids(self, obj):
        return [
            item.category.uuid
            for item in obj.doctorcategory_set.select_related("category").all()
        ]


class DoctorScheduleSerializer(serializers.ModelSerializer):
    doctor_uuid = serializers.SlugRelatedField(
        source="doctor",
        slug_field="uuid",
        queryset=DoctorProfile.objects.all(),
    )
    doctor_name = serializers.CharField(source="doctor.user.full_name", read_only=True)

    class Meta:
        model = DoctorAvailability
        fields = [
            "uuid",
            "doctor_uuid",
            "doctor_name",
            "day_of_week",
            "start_time",
            "end_time",
            "break_start_time",
            "break_end_time",
            "is_active",
        ]
        # Creating a schedule is intentionally idempotent for a doctor/day pair.
        # The model constraint remains the final database-level safeguard.
        validators = []

    def validate(self, attrs):
        doctor = attrs.get("doctor", getattr(self.instance, "doctor", None))
        day_of_week = attrs.get(
            "day_of_week",
            getattr(self.instance, "day_of_week", None),
        )
        if self.instance and doctor is not None and day_of_week is not None:
            duplicate = DoctorAvailability.objects.filter(
                doctor=doctor,
                day_of_week=day_of_week,
            ).exclude(pk=self.instance.pk)
            if duplicate.exists():
                raise serializers.ValidationError(
                    "This doctor already has a schedule for this weekday."
                )

        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        break_start = attrs.get(
            "break_start_time",
            getattr(self.instance, "break_start_time", None),
        )
        break_end = attrs.get(
            "break_end_time",
            getattr(self.instance, "break_end_time", None),
        )
        if start and end and start >= end:
            raise serializers.ValidationError("Schedule end time must be after start time.")
        if bool(break_start) != bool(break_end):
            raise serializers.ValidationError(
                "Both break start and break end are required."
            )
        if break_start and not (start <= break_start < break_end <= end):
            raise serializers.ValidationError(
                "Break time must fall inside the working schedule."
            )
        return attrs

    def create(self, validated_data):
        doctor = validated_data.pop("doctor")
        day_of_week = validated_data.pop("day_of_week")
        schedule, _ = DoctorAvailability.objects.update_or_create(
            doctor=doctor,
            day_of_week=day_of_week,
            defaults=validated_data,
        )
        return schedule


class DoctorUnavailableDateSerializer(serializers.ModelSerializer):
    doctor_uuid = serializers.SlugRelatedField(
        source="doctor",
        slug_field="uuid",
        queryset=DoctorProfile.objects.all(),
    )
    doctor_name = serializers.CharField(source="doctor.user.full_name", read_only=True)

    class Meta:
        model = DoctorUnavailableDate
        fields = ["uuid", "doctor_uuid", "doctor_name", "date", "reason"]


class AppointmentQueueSerializer(serializers.ModelSerializer):
    appointment_uuid = serializers.UUIDField(source="appointment.uuid", read_only=True)
    appointment_id = serializers.CharField(
        source="appointment.appointment_id",
        read_only=True,
    )
    patient_name = serializers.CharField(
        source="appointment.created_by.full_name",
        read_only=True,
    )
    doctor_uuid = serializers.UUIDField(source="doctor.uuid", read_only=True)
    doctor_name = serializers.CharField(source="doctor.user.full_name", read_only=True)
    status = serializers.CharField(source="appointment.status", read_only=True)

    class Meta:
        model = AppointmentQueue
        fields = [
            "uuid",
            "appointment_uuid",
            "appointment_id",
            "patient_name",
            "doctor_uuid",
            "doctor_name",
            "queue_date",
            "queue_number",
            "checked_in_at",
            "called_at",
            "status",
        ]
