from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from apps.blindtest import engine
from apps.blindtest.models import Game
from apps.catalog.i18n import tr, tr_reason
from apps.catalog.index import search_aroma, search_guess
from apps.catalog.models import WineProfile
from apps.catalog.text import normalize


class EnglishTests(TestCase):
    """Le site en anglais : interface, contenu de la base, recherche et jeu."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())

    def setUp(self):
        translation.activate("fr")

    def tearDown(self):
        translation.activate(settings.LANGUAGE_CODE)  # une requête en anglais laisse la langue active

    def get(self, url):
        return self.client.get(url, HTTP_ACCEPT_LANGUAGE="en")

    def test_compiled_catalogs_are_shipped(self):
        folder = Path(settings.BASE_DIR) / "locale" / "en" / "LC_MESSAGES"
        for name in ("django.po", "django.mo", "djangojs.po", "djangojs.mo"):
            self.assertTrue((folder / name).exists(), name)

    def test_french_is_the_default(self):
        page = self.client.get(reverse("home"))
        self.assertContains(page, '<html lang="fr">')
        self.assertContains(page, "Les défis du jour")

    def test_pages_in_english(self):
        self.assertContains(self.get(reverse("home")), '<html lang="en">')
        self.assertContains(self.get(reverse("home")), "Today's challenges")
        page = self.get(reverse("catalog:profile", args=["chablis-blanc"]))
        self.assertContains(page, "On the nose")
        self.assertContains(page, "Oyster shell")          # arôme traduit
        self.assertContains(page, "Kimmeridgian marl")     # description traduite
        self.assertContains(page, "Oysters")               # accords traduits
        self.assertNotContains(page, "Encépagement")
        page = self.get(reverse("molecules:molecule", args=["acetate-disoamyle"]))
        self.assertContains(page, "Isoamyl acetate")
        self.assertContains(page, "Formed during the fermentation of every wine")

    def test_language_switch(self):
        r = self.client.post(reverse("set_language"), {"language": "en", "next": "/le-nez/"})
        self.assertRedirects(r, "/le-nez/")
        self.assertContains(self.client.get("/le-nez/"), "The Nose")
        self.client.post(reverse("set_language"), {"language": "fr", "next": "/le-nez/"})
        self.assertContains(self.client.get("/le-nez/"), "La roue des arômes")

    def test_apis_follow_the_language(self):
        data = self.get(reverse("explorer:api_search") + "?q=viol").json()
        self.assertIn("violet", [r["label"] for r in data["results"]])
        data = self.client.get(reverse("explorer:api_search") + "?q=viol").json()
        self.assertIn("violette", [r["label"] for r in data["results"]])
        self.assertIn(b"gettext", self.get(reverse("javascript-catalog")).content)

    def test_search_accepts_both_languages(self):
        self.assertEqual(search_guess("Burgundy")[0].label, "Bourgogne")
        self.assertEqual(search_guess("red")[0].kind, "color")
        self.assertEqual(search_aroma("blackcurrant")[0].label, "cassis")
        self.assertEqual(search_aroma("cassis")[0].label, "cassis")

    def test_reason_labels(self):
        with translation.override("en"):
            self.assertEqual(tr_reason("Syrah (95 % de l'encépagement)"), "Syrah (95% of the blend)")
            self.assertEqual(tr_reason("Au nez : violette (dominant)"), "On the nose: violet (dominant)")
            self.assertEqual(tr_reason("Vin rouge"), "Red wine")
            self.assertEqual(tr("poivre noir"), "black pepper")
        self.assertEqual(tr_reason("Au nez : violette (dominant)"), "Au nez : violette (dominant)")

    def test_blind_test_in_english(self):
        profile = WineProfile.objects.get(slug="chablis-blanc")
        game = Game.objects.create(profile=profile, max_attempts=8)
        with translation.override("en"):
            guess = engine.play(game, "Burgundy")
            self.assertEqual(guess.verdict, "hit")
            self.assertIn("Burgundy", guess.feedback)
            self.assertEqual(guess.label, "Bourgogne")  # stocké en français, traduit à l'affichage
            guess = engine.play(game, "white")
            self.assertEqual(guess.label, "Blanc")
            sheet = engine.tasting_sheet(game)
            self.assertIn("lemon", [a["name"] for a in sheet["aromas"]])

    def test_english_clues_never_name_the_answer(self):
        with translation.override("en"):
            for p in WineProfile.objects.select_related("appellation__region__parent"):
                t = engine.Target.of(p)
                text = tr(p.description) + " " + ", ".join(tr(x) for x in p.pairings)
                masked = normalize(engine.mask_text(text, t))
                names = [t.appellation.name, t.region.name, tr(t.region.name)] + [g.name for g in t.main_grapes]
                for name in names:
                    self.assertNotIn(normalize(name), masked, f"{p.slug} : « {name} » visible")

    def test_every_string_is_translated(self):
        from babel.messages import pofile

        folder = Path(settings.BASE_DIR) / "locale" / "en" / "LC_MESSAGES"
        for name in ("django.po", "djangojs.po"):
            with (folder / name).open("rb") as fh:
                missing = [m.id for m in pofile.read_po(fh) if m.id and not m.string]
            self.assertEqual(missing, [], name)
