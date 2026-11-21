from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import translation

from apps.catalog.models import WineProfile
from apps.embeddings import compare


class CompareTests(TestCase):
    """Page Comparer : deux vins face à face."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", country="all", stdout=StringIO())

    def tearDown(self):
        translation.activate("fr")

    def wines(self, a="barolo-rouge", b="gevrey-chambertin-rouge"):
        return WineProfile.objects.get(slug=a), WineProfile.objects.get(slug=b)

    def test_duel_page(self):
        r = self.client.get("/comparer/barolo-rouge/gevrey-chambertin-rouge/")
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        for part in ("duel-gauge", "duel-radar", "duel-nose--wide", "duel-nose--narrow", "Tanins"):
            self.assertIn(part, html)

    def test_start_and_form_redirect(self):
        r = self.client.get("/comparer/")
        self.assertRedirects(r, "/comparer/barolo-rouge/gevrey-chambertin-rouge/")
        r = self.client.get("/comparer/?a=chablis-blanc&b=meursault-blanc")
        self.assertRedirects(r, "/comparer/chablis-blanc/meursault-blanc/")

    def test_unknown_and_same_wine(self):
        self.assertEqual(self.client.get("/comparer/barolo-rouge/inconnu/").status_code, 404)
        r = self.client.get("/comparer/barolo-rouge/barolo-rouge/")
        self.assertContains(r, "deux vins différents")
        self.assertNotContains(r, "duel-gauge")

    def test_english(self):
        r = self.client.get("/en/comparer/barolo-rouge/gevrey-chambertin-rouge/")
        self.assertContains(r, "Closeness")
        self.assertContains(r, "compared")

    def test_proximity_is_a_percentile(self):
        a, b = self.wines()
        sp = compare.space()
        self.assertEqual(compare.proximity(sp, a, a), compare.proximity(sp, a, a))
        p_near = compare.proximity(sp, *self.wines("barolo-rouge", "barbaresco-rouge"))
        p_far = compare.proximity(sp, *self.wines("barolo-rouge", "sauternes-blanc"))
        self.assertTrue(0 <= p_far < 25 < 90 <= p_near <= 100, (p_far, p_near))
        self.assertEqual(compare.band(p_near), "Très proches")
        self.assertEqual(compare.band(p_far), "Opposés")

    def test_nose_splits_and_signature(self):
        a, b = self.wines()
        nose = compare.nose(compare.space(), a, b)
        names = lambda items: {x.slug for x in items}  # noqa: E731
        self.assertEqual(names(nose.common), {"reglisse", "violette", "cuir"})
        self.assertIn("rose", names(nose.only_a))
        self.assertIn("cerise-noire", names(nose.only_b))
        self.assertFalse(names(nose.only_a) & names(nose.only_b))
        for x, y in nose.neighbours:
            self.assertIn(x, names(nose.only_a))
            self.assertIn(y, names(nose.only_b))
        self.assertEqual(compare.signature(b, a)["name"], "cinnamate d'éthyle")

    def test_mouth_deltas(self):
        d = compare.duel(*self.wines())
        tannin = next(m for m in d["mouth"] if str(m["label"]) == "Tanins")
        self.assertEqual((tannin["a"], tannin["b"], tannin["delta"]), (5, 3, 2))

    def test_menu(self):
        html = self.client.get("/catalogue/").content.decode()
        self.assertIn('href="/comparer/"', html)
        self.assertIn("Trouve mon vin", html)
        self.assertIn("nav-group--games", html)
        self.assertNotIn('href="/graphe/"', html)  # graphe caché par défaut
        self.assertEqual(self.client.get("/graphe/").status_code, 200)  # mais toujours servi

    @override_settings(HIDDEN_SECTIONS=[])
    def test_graph_can_be_shown_again(self):
        self.assertIn('href="/graphe/"', self.client.get("/catalogue/").content.decode())

    def test_sitemap_lists_featured_duels(self):
        xml = self.client.get("/sitemap.xml").content.decode()
        self.assertIn("/comparer/barolo-rouge/gevrey-chambertin-rouge/", xml)
        self.assertNotIn("/graphe/<", xml)


class MapGroupsTests(TestCase):
    """Carte des goûts : les vins sont rangés en groupes nommés (vue d'ensemble sur téléphone)."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", country="all", stdout=StringIO())

    def test_every_wine_has_a_named_group(self):
        data = self.client.get("/carte/api/carte/").json()
        groups = {g["id"]: g for g in data["groups"]}
        self.assertGreaterEqual(len(groups), 6)
        wines = [n for n in data["nodes"] if n["type"] == "profile"]
        self.assertTrue(all(f"group:{n['group']}" in groups for n in wines))
        self.assertEqual(sum(g["n"] for g in groups.values()), len(wines))
        labels = [g["label"] for g in groups.values()]
        self.assertIn("Bulles", labels)
        self.assertTrue(any(lab.startswith("Rouges · ") for lab in labels))


class CompareSearchTests(TestCase):
    """Recherche des vins à comparer : par nom, appellation, région ou cépage."""

    @classmethod
    def setUpTestData(cls):
        from io import StringIO

        from django.core.management import call_command
        call_command("load_seed", country="all", stdout=StringIO())

    def find(self, q):
        return [r["slug"] for r in self.client.get("/comparer/api/vins/", {"q": q}).json()["results"]]

    def test_by_name_without_accents(self):
        self.assertEqual(self.find("cote rotie")[0], "cote-rotie-rouge")

    def test_by_grape_and_words(self):
        self.assertIn("barolo-rouge", self.find("nebbiolo"))
        self.assertTrue(all("blanc" in s for s in self.find("chablis blanc")))

    def test_empty(self):
        self.assertEqual(self.find(""), [])
