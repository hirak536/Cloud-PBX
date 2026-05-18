from django.apps import AppConfig


class DestinationsConfig(AppConfig):
    name = 'apps.destinations'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        import apps.destinations.signals  # noqa
