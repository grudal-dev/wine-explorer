from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.analytics"
    verbose_name = "Statistiques de visite"

    def ready(self):
        from django.contrib.auth.signals import user_logged_in

        from .tracking import track

        def on_login(sender, request, user, **kwargs):
            if request is not None:
                track(request, "login")

        user_logged_in.connect(on_login, dispatch_uid="analytics_login", weak=False)
