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
from django.utils import translation

# Ordre = ordre de repli pour la page d'accueil quand « / » n'est pas servie.
SECTIONS = {
    "molecules": "/molecules/",
    "carte": "/carte/",
    "comparer": "/comparer/",
    "catalogue": "/catalogue/",
    "graphe": "/graphe/",
    "blindtest": "/blind-test/",
    "nose": "/le-nez/",
    "chaudfroid": "/chaud-froid/",
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


def visible() -> frozenset[str]:
    """Sections servies et montrées : `DJANGO_HIDDEN_SECTIONS` (défaut : graphe) en retire du menu, des liens
    et du plan du site sans les fermer ; une section cachée reste joignable par son adresse."""
    return enabled() - frozenset(getattr(settings, "HIDDEN_SECTIONS", []))


def language_of(path: str) -> str | None:
    """Langue annoncée par le préfixe d'URL (`/en/…`) ; `None` pour le français, qui n'en a pas."""
    code = translation.get_language_from_path(str(path))
    return code if code in dict(settings.LANGUAGES) and code != settings.LANGUAGE_CODE else None


def strip_language(path: str) -> str:
    """`/en/molecules/` → `/molecules/` : les sections se reconnaissent à leur chemin sans langue."""
    code = language_of(path)
    return (str(path)[len(code) + 1 :] or "/") if code else str(path)


def path_enabled(path: str) -> bool:
    path = strip_language(path)
    on = enabled()
    return all(name in on for name, prefix in SECTIONS.items() if str(path).startswith(prefix))


class SectionGateMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        on = enabled()
        if len(on) < len(SECTIONS):
            path = strip_language(request.path_info)
            if path == "/":
                landing = next(name for name in SECTIONS if name in on)
                prefix = f"/{language_of(request.path_info)}" if language_of(request.path_info) else ""
                return redirect(prefix + SECTIONS[landing])
            if not path_enabled(path):
                raise Http404("Section non publique")
        return self.get_response(request)


def context(request):
    return {"sections": visible(), "path_no_lang": strip_language(request.path)}
