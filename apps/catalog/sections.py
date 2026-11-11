"""Sections publiques du site.

`DJANGO_PUBLIC_SECTIONS` (liste séparée par des virgules) restreint ce que le site sert : les autres
sections répondent 404 et disparaissent des menus. Vide ou absent : tout est servi (développement).
Exemple de déploiement partiel : `molecules,carte,catalogue` (le catalogue reste servi car les fiches
molécules et la carte renvoient vers les fiches de vins, d'appellations, de cépages et d'arômes).
"""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import Http404
from django.shortcuts import redirect

# Ordre = ordre de repli pour la page d'accueil quand « / » n'est pas servie.
SECTIONS = {
    "molecules": "/molecules/",
    "carte": "/carte/",
    "catalogue": "/catalogue/",
    "graphe": "/graphe/",
    "blindtest": "/blind-test/",
    "nose": "/le-nez/",
    "compte": "/compte/",
}


def enabled() -> frozenset[str]:
    configured = list(getattr(settings, "PUBLIC_SECTIONS", []))
    unknown = set(configured) - set(SECTIONS)
    if unknown:
        raise ImproperlyConfigured(
            f"DJANGO_PUBLIC_SECTIONS : section(s) inconnue(s) {sorted(unknown)}. "
            f"Valeurs possibles : {', '.join(SECTIONS)}."
        )
    return frozenset(configured) if configured else frozenset(SECTIONS)


def path_enabled(path: str) -> bool:
    on = enabled()
    return all(name in on for name, prefix in SECTIONS.items() if str(path).startswith(prefix))


class SectionGateMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        on = enabled()
        if len(on) < len(SECTIONS):
            path = request.path_info
            if path == "/":
                landing = next(name for name in SECTIONS if name in on)
                return redirect(SECTIONS[landing])
            if not path_enabled(path):
                raise Http404("Section non publique")
        return self.get_response(request)


def context(request):
    return {"sections": enabled()}
