from django.contrib import admin

from .models import LabRequest, LabRequestItem, LabResult, LabTestType


class LabRequestItemInline(admin.TabularInline):
    model = LabRequestItem
    extra = 0


@admin.register(LabTestType)
class LabTestTypeAdmin(admin.ModelAdmin):
    list_display = ("uuid", "name", "is_active", "updated_at")
    search_fields = ("name", "description")


@admin.register(LabRequest)
class LabRequestAdmin(admin.ModelAdmin):
    list_display = ("uuid", "consultation", "doctor", "patient", "status", "requested_at")
    list_filter = ("status", "requested_at")
    search_fields = ("uuid", "consultation__uuid", "patient__user__first_name", "patient__user__last_name")
    inlines = [LabRequestItemInline]


@admin.register(LabRequestItem)
class LabRequestItemAdmin(admin.ModelAdmin):
    list_display = ("uuid", "lab_request", "test_type")
    search_fields = ("uuid", "test_type__name", "lab_request__uuid")


@admin.register(LabResult)
class LabResultAdmin(admin.ModelAdmin):
    list_display = ("uuid", "request_item", "verified_by", "verified_at")
    search_fields = ("uuid", "request_item__uuid", "request_item__test_type__name")

