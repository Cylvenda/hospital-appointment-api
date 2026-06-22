from rest_framework.routers import DefaultRouter

from .views import InvoiceItemViewSet, InvoiceViewSet

router = DefaultRouter()
router.register(r"invoices", InvoiceViewSet, basename="invoice")
router.register(r"invoice-items", InvoiceItemViewSet, basename="invoice-item")

urlpatterns = router.urls

