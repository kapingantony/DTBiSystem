from django.apps import AppConfig
from django.db.models import signals


class StaffConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'staff'

    def ready(self):
        import staff.signals  # noqa: F401
