"""Référencement : balises communes, robots.txt et plan du site.

Les URL du plan du site suivent `DJANGO_PUBLIC_SECTIONS` : une section non servie (404) n'y figure pas.
`SITE_URL` (ex. https://www.exemple.fr, déjà utilisé par la newsletter) fixe l'adresse canonique ; sans elle,
on prend celle de la requête.
"""

from types import SimpleNamespace

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.http import HttpResponse
from django.templatetags.static import static
from django.urls import translate_url, reverse

from . import sections
from .models import Appellation, Aroma, Grape, Region, WineProfile

# Pages sans intérêt pour un moteur (jeux, API, comptes, fragments HTML chargés par le graphe).
DISALLOWED = (
    "/admin/",
    "/api/",
    "/compte/",
    "/i18n/",
    "/jsi18n/",
    "/blind-test/partie/",
    "/blind-test/nouvelle-partie/",
    "/blind-test/api/",
    "/graphe/api/",
    "/graphe/noeud/",
    "/molecules/api/",
    "/molecules/fiche/",
    "/carte/api/",
    "/comparer/api/",
    "/carte/fiche/",
    "/le-nez/api/",
)


def configured_site_url() -> str:
    """`SITE_URL` si elle a été renseignée ; sa valeur par défaut (poste de développement) ne compte pas."""
    url = getattr(settings, "SITE_URL", "")
    return "" if url in ("", "http://localhost:8000") else url


def site_base(request) -> str:
    return configured_site_url() or f"{request.scheme}://{request.get_host()}"


def alternates(request, base: str) -> list[tuple[str, str]]:
    """Les adresses de la page dans chaque langue, pour `hreflang`. Vide si la page n'existe que dans une langue."""
    if not getattr(request, "resolver_match", None):
        return []
    urls = {code: base + translate_url(request.path, code) for code, _name in settings.LANGUAGES}
    return list(urls.items()) if len(set(urls.values())) == len(urls) else []


def context(request):
    base = site_base(request)
    links = alternates(request, base)
    return {
        "canonical_url": base + request.path,
        "site_url": base,
        "og_image_url": base + static("img/og.png"),
        "hreflang_links": links,
        "hreflang_default": dict(links).get(settings.LANGUAGE_CODE, ""),
    }


def robots_txt(request):
    others = [code for code, _name in settings.LANGUAGES if code != settings.LANGUAGE_CODE]
    paths = [p for path in DISALLOWED for p in (path, *(f"/{code}{path}" for code in others))]
    lines = ["User-agent: *", *(f"Disallow: {p}" for p in paths), "", f"Sitemap: {site_base(request)}/sitemap.xml", ""]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


class _Base(Sitemap):
    protocol = None  # celui de la requête (https derrière le proxy, voir SECURE_PROXY_SSL_HEADER)
    # Une entrée par langue, chacune avec ses alternates (xhtml:link hreflang, dont x-default).
    i18n = True
    alternates = True
    x_default = True

    def get_urls(self, page=1, site=None, protocol=None):
        # Le domaine canonique, s'il est défini, l'emporte sur celui de la requête.
        if configured_site_url():
            scheme, _, host = configured_site_url().partition("://")
            site, protocol = SimpleNamespace(domain=host), scheme
        return super().get_urls(page=page, site=site, protocol=protocol)

    def _on(self, path: str) -> bool:
        hidden = sections.enabled() - sections.visible()
        return sections.path_enabled(path) and not any(
            sections.strip_language(path).startswith(sections.SECTIONS[name]) for name in hidden)


class StaticPages(_Base):
    priority = 0.8
    changefreq = "weekly"
    names = (
        "home",
        "catalog:index",
        "catalog:grapes",
        "catalog:aromas",
        "catalog:sources",
        "molecules:explorer",
        "molecules:list",
        "molecules:bibliography",
        "blindtest:home",
        "hotcold:game",
        "nose:nose",
        "embeddings:map",
        "explorer:explorer",
    )

    def items(self):
        return [n for n in self.names if self._on(reverse(n))]

    def location(self, name):
        return reverse(name)


class _Model(_Base):
    changefreq = "monthly"
    section_path = "/catalogue/"

    def items(self):
        return self.queryset() if self._on(self.section_path) else []


class Profiles(_Model):
    priority = 0.9

    def queryset(self):
        return WineProfile.objects.order_by("slug")


class Appellations(_Model):
    priority = 0.8

    def queryset(self):
        return Appellation.objects.order_by("slug")


class Regions(_Model):
    priority = 0.7

    def queryset(self):
        return Region.objects.order_by("slug")


class Grapes(_Model):
    priority = 0.7

    def queryset(self):
        return Grape.objects.order_by("slug")


class Aromas(_Model):
    priority = 0.5

    def queryset(self):
        return Aroma.objects.order_by("slug")


class Molecules(_Model):
    priority = 0.6
    section_path = "/molecules/"

    def queryset(self):
        from apps.molecules.models import Molecule

        return Molecule.objects.order_by("slug")


class NaturalSources(_Model):
    priority = 0.5
    section_path = "/molecules/"

    def queryset(self):
        from apps.molecules.models import NaturalSource

        return NaturalSource.objects.order_by("slug")


class Duels(_Base):
    """Les duels mis en avant de la page Comparer (les paires dont les deux vins existent)."""
    priority = 0.6
    changefreq = "monthly"

    def items(self):
        from apps.embeddings.compare import FEATURED

        if not self._on("/comparer/"):
            return []
        known = set(WineProfile.objects.values_list("slug", flat=True))
        return [pair for pair in FEATURED if set(pair) <= known]

    def location(self, pair):
        return reverse("compare:duel", args=pair)


SITEMAPS = {
    "pages": StaticPages,
    "vins": Profiles,
    "appellations": Appellations,
    "regions": Regions,
    "cepages": Grapes,
    "aromes": Aromas,
    "molecules": Molecules,
    "nature": NaturalSources,
    "duels": Duels,
}
