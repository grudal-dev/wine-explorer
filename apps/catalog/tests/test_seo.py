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
        self.assertIn("http://exemple.fr/en/catalogue/vins/barolo-rouge/", locs)
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


class EnglishSeoTests(TestCase):
    """L'anglais a ses propres adresses (/en/…), reliées au français par hreflang."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", country="all", stdout=StringIO())

    def links(self, html):
        return dict(re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)">', html))

    def test_each_language_has_its_own_url_and_content(self):
        fr = self.client.get("/catalogue/vins/barolo-rouge/").content.decode()
        en = self.client.get("/en/catalogue/vins/barolo-rouge/").content.decode()
        self.assertIn('<html lang="fr">', fr)
        self.assertIn('<html lang="en">', en)
        self.assertIn("Encépagement typique", fr)
        self.assertNotIn("Encépagement typique", en)
        self.assertTrue(meta(en, "name", "description").startswith("The king of Italian wines"))

    def test_hreflang_links_both_ways_and_canonical_is_self(self):
        for path, other in (("/catalogue/vins/barolo-rouge/", "/en/catalogue/vins/barolo-rouge/"),
                            ("/en/catalogue/vins/barolo-rouge/", "/catalogue/vins/barolo-rouge/")):
            html = self.client.get(path, HTTP_HOST="exemple.fr").content.decode()
            links = self.links(html)
            self.assertEqual(links["fr"], "http://exemple.fr/catalogue/vins/barolo-rouge/")
            self.assertEqual(links["en"], "http://exemple.fr/en/catalogue/vins/barolo-rouge/")
            self.assertEqual(links["x-default"], links["fr"])
            self.assertIn(f'<link rel="canonical" href="http://exemple.fr{path}">', html)
            self.assertNotEqual(path, other)

    def test_internal_links_and_assets_stay_in_english(self):
        html = self.client.get("/en/catalogue/vins/barolo-rouge/").content.decode()
        self.assertIn('href="/en/molecules/"', html)
        self.assertIn('href="/en/catalogue/cepages/nebbiolo/"', html)
        self.assertNotIn('href="/molecules/"', html)
        self.assertIn('<script src="/en/jsi18n/">', html)
        graph = self.client.get("/en/molecules/").content.decode()
        self.assertIn('data-api="/en/molecules/api/graphe/"', graph)

    def test_menu_marks_the_current_section_in_english(self):
        html = self.client.get("/en/molecules/").content.decode()
        self.assertIn('<a href="/en/molecules/" aria-current="page">', html)

    def test_pages_without_a_translation_get_no_hreflang(self):
        html = self.client.get("/robots.txt").content.decode()
        self.assertNotIn("hreflang", html)
        self.assertEqual(self.client.get("/nimporte-quoi/").status_code, 404)

    def test_sitemap_pairs_every_url_with_its_translation(self):
        res = self.client.get("/sitemap.xml", HTTP_HOST="exemple.fr")
        root = ET.fromstring(res.content)
        xhtml = "{http://www.w3.org/1999/xhtml}link"
        entries = {u.find("s:loc", NS).text: {a.get("hreflang"): a.get("href") for a in u.findall(xhtml)}
                   for u in root.findall("s:url", NS)}
        self.assertEqual(len([u for u in entries if "/en/" in u]), len([u for u in entries if "/en/" not in u]))
        alt = entries["http://exemple.fr/en/catalogue/aromes/violette/"]
        self.assertEqual(alt["fr"], "http://exemple.fr/catalogue/aromes/violette/")
        self.assertEqual(alt["x-default"], alt["fr"])

    def test_robots_hides_the_english_private_areas_too(self):
        text = self.client.get("/robots.txt").content.decode()
        for path in ("/compte/", "/en/compte/", "/en/blind-test/partie/", "/en/molecules/fiche/", "/api/"):
            self.assertIn(f"Disallow: {path}", text)
        self.assertNotIn("Disallow: /en/catalogue", text)

    @override_settings(PUBLIC_SECTIONS=["molecules", "carte", "catalogue"])
    def test_section_gate_works_under_the_english_prefix(self):
        self.assertEqual(self.client.get("/en/molecules/").status_code, 200)
        self.assertEqual(self.client.get("/en/graphe/").status_code, 404)
        self.assertEqual(self.client.get("/en/compte/connexion/").status_code, 404)
        self.assertRedirects(self.client.get("/en/"), "/en/molecules/", fetch_redirect_response=False)
        self.assertRedirects(self.client.get("/"), "/molecules/", fetch_redirect_response=False)
        locs = [e.text for e in ET.fromstring(self.client.get("/sitemap.xml").content).findall("s:url/s:loc", NS)]
        self.assertFalse([loc for loc in locs if "/graphe" in loc or "/blind-test" in loc])
        self.assertTrue([loc for loc in locs if "/en/molecules/" in loc])

    def test_home_sends_english_browsers_to_english_only(self):
        en = {"HTTP_ACCEPT_LANGUAGE": "en-GB,en;q=0.9"}
        self.assertRedirects(self.client.get("/", **en), "/en/", fetch_redirect_response=False)
        self.assertEqual(self.client.get("/").status_code, 200)  # robots : pas de préférence
        self.assertEqual(self.client.get("/", HTTP_ACCEPT_LANGUAGE="fr-FR,fr;q=0.9").status_code, 200)
        self.assertEqual(self.client.get("/en/", **en).status_code, 200)
        # Une page profonde n'est jamais redirigée : l'adresse partagée garde sa langue.
        self.assertEqual(self.client.get("/catalogue/", **en).status_code, 200)
        # Qui a choisi le français (cookie) y reste, même avec un navigateur anglais.
        self.client.cookies["django_language"] = "fr"
        self.assertEqual(self.client.get("/", **en).status_code, 200)

    def test_mobile_api_still_follows_accept_language(self):
        data = self.client.get("/api/v1/wines/chablis-blanc/", HTTP_ACCEPT_LANGUAGE="en").json()
        self.assertEqual(data["color_label"], "White")
        data = self.client.get("/api/v1/wines/chablis-blanc/", HTTP_ACCEPT_LANGUAGE="fr").json()
        self.assertEqual(data["color_label"], "Blanc")
