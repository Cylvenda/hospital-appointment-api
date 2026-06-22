from django.contrib import admin

from .models import Invoice, InvoiceItem


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "patient", "consultation", "status", "total_amount", "issued_at", "paid_at")
    list_filter = ("status", "issued_at")
    search_fields = ("invoice_number", "patient__user__first_name", "patient__user__last_name", "consultation__uuid")
    inlines = [InvoiceItemInline]


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = ("uuid", "invoice", "item_type", "description", "quantity", "unit_price", "amount")
    list_filter = ("item_type",)
    search_fields = ("uuid", "description", "invoice__invoice_number")

