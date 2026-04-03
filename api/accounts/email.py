from djoser import email
from django.conf import settings


class CustomActivationEmail(email.ActivationEmail):
    template_name = "email/activations.html"

    def get_context_data(self):
        context = super().get_context_data()
        context["site_name"] = settings.SITE_NAME
        return context
