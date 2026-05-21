from django.apps import AppConfig


class CustomDestinationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.custom_destinations'

    def ready(self):
        # Register signal handlers
        from . import signals  # noqa: F401
