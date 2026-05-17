from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'api.accounts'

    def ready(self):
        import api.accounts.signals
