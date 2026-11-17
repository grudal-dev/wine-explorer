import time

from .tracking import record_pageview


class AnalyticsMiddleware:
    """Enregistre chaque page HTML servie. À placer après l'authentification (pour exclure l'équipe)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        record_pageview(request, response, int((time.monotonic() - start) * 1000))
        return response
