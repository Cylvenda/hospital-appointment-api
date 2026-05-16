from djoser import email
from django.conf import settings
from datetime import datetime


class ContextMixin:
    def get_context_data(self):
        context = super().get_context_data()
        context["site_name"] = settings.SITE_NAME
        context["year"] = datetime.now().year
        return context


class CustomActivationEmail(ContextMixin, email.ActivationEmail):
    template_name = "email/activations.html"


class CustomConfirmationEmail(ContextMixin, email.ConfirmationEmail):
    template_name = "email/confirmation.html"


class CustomPasswordResetEmail(ContextMixin, email.PasswordResetEmail):
    template_name = "email/password_reset.html"


class CustomPasswordChangedConfirmationEmail(ContextMixin, email.PasswordChangedConfirmationEmail):
    template_name = "email/password_changed_confirmation.html"
