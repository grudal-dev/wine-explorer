from django.apps import AppConfig


class MoleculesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.molecules"
    verbose_name = "Molécules"

    def ready(self):
        from . import checks  # noqa: F401 - enregistre la vérification au démarrage
