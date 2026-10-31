"""Cache des réponses JSON, invalidé dès que les données changent.

`cache_page` garde une réponse 5 minutes quoi qu'il arrive : avec le cache mémoire par processus,
un `load_seed` lancé dans un autre terminal ne le vide pas, et le serveur continue de servir un
graphe sans molécules. Ici, la clé contient la version des données (nombre de profils, de molécules,
de liens…) : recharger les données change la clé, donc la réponse.
"""

import hashlib
from functools import wraps

from django.core.cache import cache
from django.http import HttpResponse


def _data_version() -> tuple:
    from apps.explorer.graph import _version

    return _version()


def cache_json(timeout: int, prefix: str):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            raw = f"{_data_version()}|{request.get_full_path()}"
            key = f"{prefix}:{hashlib.sha1(raw.encode()).hexdigest()}"
            hit = cache.get(key)
            if hit is not None:
                status, content = hit
                return HttpResponse(content, status=status, content_type="application/json")
            response = view(request, *args, **kwargs)
            if response.status_code < 500:
                cache.set(key, (response.status_code, response.content), timeout)
            return response

        return wrapped

    return decorator
