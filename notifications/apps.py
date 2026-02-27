from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "notifications"

    def ready(self):
        # Register model signal handlers for status-driven notifications.
        from . import signals  # noqa: F401
