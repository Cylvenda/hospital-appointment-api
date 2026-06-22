from django.contrib import admin

from .models import Consultation


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ("uuid", "appointment", "doctor", "patient", "status", "started_at", "completed_at")
    list_filter = ("status", "started_at", "completed_at")
    search_fields = ("uuid", "appointment__uuid", "doctor__user__first_name", "doctor__user__last_name", "patient__user__first_name", "patient__user__last_name")

