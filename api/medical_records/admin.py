from django.contrib import admin

from .models import Diagnosis, PatientMedicalRecord


@admin.register(PatientMedicalRecord)
class PatientMedicalRecordAdmin(admin.ModelAdmin):
    list_display = ("uuid", "patient", "blood_group", "weight", "height", "bmi", "updated_at")
    search_fields = ("uuid", "patient__user__first_name", "patient__user__last_name")


@admin.register(Diagnosis)
class DiagnosisAdmin(admin.ModelAdmin):
    list_display = ("uuid", "consultation", "disease_name", "type", "diagnosed_at")
    list_filter = ("type", "diagnosed_at")
    search_fields = ("uuid", "disease_name", "icd10_code", "consultation__uuid")

