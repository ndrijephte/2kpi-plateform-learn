from django.apps import AppConfig

class ComptesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.comptes"
    verbose_name = "Comptes & profils"

    def ready(self):
        from . import signals  # noqa: F401
