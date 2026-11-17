import time

from django.conf import settings

from .tracking import IGNORE_COOKIE, record_pageview, set_ignore_cookie


class AnalyticsMiddleware:
    """Enregistre chaque page HTML servie. À placer après l'authentification (pour exclure l'équipe)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        record_pageview(request, response, int((time.monotonic() - start) * 1000))
        # Un appareil sur lequel l'équipe s'est connectée n'est plus compté, même déconnecté ensuite.
        user = getattr(request, "user", None)
        staff = user is not None and user.is_authenticated and user.is_staff
        marked = request.COOKIES.get(IGNORE_COOKIE) == "1"
        if staff and not marked and not getattr(settings, "ANALYTICS_TRACK_STAFF", False):
            set_ignore_cookie(response, request)
        return response
