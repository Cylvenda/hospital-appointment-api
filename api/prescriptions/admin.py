from django.contrib import admin

from .models import Prescription, PrescriptionItem


class PrescriptionItemInline(admin.TabularInline):
    model = PrescriptionItem
    extra = 0


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ("uuid", "consultation", "doctor", "patient", "created_at")
    list_filter = ("created_at",)
    search_fields = ("uuid", "consultation__uuid", "patient__user__first_name", "patient__user__last_name")
    inlines = [PrescriptionItemInline]


@admin.register(PrescriptionItem)
class PrescriptionItemAdmin(admin.ModelAdmin):
    list_display = ("uuid", "prescription", "medicine_name", "dosage", "frequency", "duration")
    search_fields = ("uuid", "medicine_name", "prescription__uuid")

