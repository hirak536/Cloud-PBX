from django.apps import AppConfig


class ClientApiConfig(AppConfig):
    name = 'apps.client_api'
    label = 'client_api'
    verbose_name = 'Client API'

    def ready(self):
        import apps.client_api.signals  # noqa: F401
