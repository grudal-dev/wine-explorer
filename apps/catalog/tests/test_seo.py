import re
import xml.etree.ElementTree as ET
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.catalog.models import Aroma, Grape, Region, WineProfile
from apps.catalog.seo import DISALLOWED

NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def meta(html, attr, name):
    m = re.search(rf'<meta {attr}="{name}" content="([^"]*)"', html)
    return m.group(1) if m else None


class SeoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", country="all", stdout=StringIO())

    def locs(self, **extra):
        res = self.client.get("/sitemap.xml", **extra)
        self.assertEqual(res.status_code, 200)
        return [e.text for e in ET.fromstring(res.content).findall("s:url/s:loc", NS)]

    def test_robots_points_to_sitemap_and_hides_private_areas(self):
        res = self.client.get("/robots.txt", HTTP_HOST="exemple.fr")
        text = res.content.decode()
        self.assertEqual(res["Content-Type"], "text/plain; charset=utf-8")
        self.assertIn("Sitemap: http://exemple.fr/sitemap.xml", text)
        for path in DISALLOWED:
            self.assertIn(f"Disallow: {path}", text)
        self.assertNotIn("Disallow: /catalogue", text)

    def test_sitemap_lists_every_public_page_once(self):
        locs = self.locs(HTTP_HOST="exemple.fr")
        self.assertEqual(len(locs), len(set(locs)))
        for obj in (WineProfile.objects.first(), Region.objects.first(), Grape.objects.first(), Aroma.objects.first()):
            self.assertIn("http://exemple.fr" + obj.get_absolute_url(), locs)
        self.assertTrue(any("/vins/barolo" in loc for loc in locs), "l'Italie manque au plan du site")
        self.assertFalse([loc for loc in locs if any(d in loc for d in ("/compte/", "/api/", "/admin/", "/partie/"))])

    @override_settings(SITE_URL="https://www.exemple.fr")
    def test_site_url_wins_over_request_host(self):
        self.assertTrue(all(loc.startswith("https://www.exemple.fr/") for loc in self.locs()))
        self.assertIn("Sitemap: https://www.exemple.fr/sitemap.xml", self.client.get("/robots.txt").content.decode())

    @override_settings(PUBLIC_SECTIONS=["molecules", "carte", "catalogue"])
    def test_sitemap_follows_public_sections(self):
        locs = self.locs()
        self.assertFalse([loc for loc in locs if "/blind-test" in loc or "/graphe" in loc])
        self.assertTrue([loc for loc in locs if "/molecules/" in loc])
        self.assertTrue([loc for loc in locs if "/catalogue/vins/" in loc])

    def test_profile_page_has_its_own_tags(self):
        p = WineProfile.objects.get(slug="barolo-rouge")
        html = self.client.get(p.get_absolute_url(), HTTP_HOST="exemple.fr").content.decode()
        self.assertIn("<title>Barolo rouge", html)
        self.assertTrue(meta(html, "name", "description").startswith(p.description[:40]))
        self.assertLessEqual(len(meta(html, "name", "description")), 165)
        self.assertIn(f'<link rel="canonical" href="http://exemple.fr{p.get_absolute_url()}">', html)
        self.assertEqual(meta(html, "property", "og:url"), "http://exemple.fr" + p.get_absolute_url())
        self.assertTrue(meta(html, "property", "og:image").endswith("/static/img/og.png"))

    def test_canonical_drops_query_string(self):
        html = self.client.get("/molecules/?depart=molecule:rotundone", HTTP_HOST="exemple.fr").content.decode()
        self.assertIn('<link rel="canonical" href="http://exemple.fr/molecules/">', html)

    def test_every_indexable_page_has_a_distinct_description(self):
        seen = {}
        for url in ("/", "/catalogue/", "/catalogue/cepages/", "/catalogue/aromes/", "/blind-test/", "/le-nez/",
                    "/graphe/", "/carte/", "/molecules/", "/molecules/liste/", "/catalogue/sources/",
                    WineProfile.objects.first().get_absolute_url(), Region.objects.first().get_absolute_url(),
                    Grape.objects.first().get_absolute_url(), Aroma.objects.first().get_absolute_url()):
            desc = meta(self.client.get(url).content.decode(), "name", "description")
            self.assertTrue(desc, url)
            self.assertNotIn(desc, seen, f"{url} et {seen.get(desc)} ont la même description")
            seen[desc] = url

    def test_account_pages_are_noindex(self):
        for url in ("/compte/connexion/", "/compte/inscription/", "/compte/classement/"):
            self.assertIn('<meta name="robots" content="noindex">', self.client.get(url).content.decode(), url)
        self.assertNotIn("noindex", self.client.get("/catalogue/").content.decode())
