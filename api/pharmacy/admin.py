from django.contrib import admin

from .models import Dispensing, DispensingItem, Medicine


class DispensingItemInline(admin.TabularInline):
    model = DispensingItem
    extra = 0


@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ("uuid", "name", "generic_name", "unit_price", "stock_quantity", "expiry_date")
    search_fields = ("name", "generic_name")


@admin.register(Dispensing)
class DispensingAdmin(admin.ModelAdmin):
    list_display = ("uuid", "prescription", "pharmacist", "status", "dispensed_at", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("uuid", "prescription__uuid")
    inlines = [DispensingItemInline]


@admin.register(DispensingItem)
class DispensingItemAdmin(admin.ModelAdmin):
    list_display = ("uuid", "dispensing", "medicine", "quantity")
    search_fields = ("uuid", "medicine__name", "dispensing__uuid")

