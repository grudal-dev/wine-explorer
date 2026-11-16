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
from django.urls import reverse

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
    "/carte/fiche/",
    "/le-nez/api/",
)


def configured_site_url() -> str:
    """`SITE_URL` si elle a été renseignée ; sa valeur par défaut (poste de développement) ne compte pas."""
    url = getattr(settings, "SITE_URL", "")
    return "" if url in ("", "http://localhost:8000") else url


def site_base(request) -> str:
    return configured_site_url() or f"{request.scheme}://{request.get_host()}"


def context(request):
    base = site_base(request)
    return {
        "canonical_url": base + request.path,
        "site_url": base,
        "og_image_url": base + static("img/og.png"),
    }


def robots_txt(request):
    lines = ["User-agent: *", *(f"Disallow: {path}" for path in DISALLOWED), "", f"Sitemap: {site_base(request)}/sitemap.xml", ""]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


class _Base(Sitemap):
    protocol = None  # celui de la requête (https derrière le proxy, voir SECURE_PROXY_SSL_HEADER)

    def get_urls(self, page=1, site=None, protocol=None):
        # Le domaine canonique, s'il est défini, l'emporte sur celui de la requête.
        if configured_site_url():
            scheme, _, host = configured_site_url().partition("://")
            site, protocol = SimpleNamespace(domain=host), scheme
        return super().get_urls(page=page, site=site, protocol=protocol)

    def _on(self, path: str) -> bool:
        return sections.path_enabled(path)


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


SITEMAPS = {
    "pages": StaticPages,
    "vins": Profiles,
    "appellations": Appellations,
    "regions": Regions,
    "cepages": Grapes,
    "aromes": Aromas,
    "molecules": Molecules,
    "nature": NaturalSources,
}
