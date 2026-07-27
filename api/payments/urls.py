from django.urls import path
from .views import PaymentCreateView, PaymentStatusView, payment_webhook

urlpatterns = [
    path("create/", PaymentCreateView.as_view(), name="payment-create"),
    path("webhook/", payment_webhook, name="payment-webhook"),
    path("<uuid:uuid>/status/", PaymentStatusView.as_view(), name="payment-status"),
]
