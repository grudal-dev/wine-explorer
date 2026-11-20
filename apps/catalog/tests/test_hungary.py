from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import translation

from apps.blindtest import engine
from apps.blindtest.models import Game
from apps.catalog.i18n import tr
from apps.catalog.index import search_guess
from apps.catalog.models import Appellation, WineProfile
from apps.catalog.text import normalize
from apps.molecules.models import ProfileMolecule


class HungaryTests(TestCase):
    """Tokaj (data/hu/) se charge à côté de la France et de l'Italie."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", country="all", stdout=StringIO())

    def tearDown(self):
        translation.activate("fr")  # une requête en anglais laisse la langue active

    def hungarian(self):
        return WineProfile.objects.filter(appellation__country__code="HU")

    def test_tokaj_profiles(self):
        self.assertEqual(
            sorted(self.hungarian().values_list("slug", flat=True)),
            ["tokaji-aszu", "tokaji-eszencia", "tokaji-furmint-sec", "tokaji-szamorodni-doux", "tokaji-szamorodni-sec"],
        )
        for p in self.hungarian().prefetch_related("profile_grapes"):
            self.assertEqual(sum(pg.share for pg in p.profile_grapes.all()), 100, p.name)
            self.assertTrue(ProfileMolecule.objects.filter(profile=p).exists(), p.name)

    def test_sotolon_in_dry_szamorodni(self):
        """Élevé sous voile (style oxydatif) : le sotolon y est un marqueur, comme dans le vin jaune."""
        link = ProfileMolecule.objects.get(profile__slug="tokaji-szamorodni-sec", molecule__slug="sotolon")
        self.assertEqual(link.strength, 3)

    def test_guesses_resolve(self):
        for label, expected in [("Tokaji", "Tokaj"), ("Furmint", "Furmint"), ("Harslevelu", "Hárslevelű"),
                                ("Sárgamuskotály", "Muscat à petits grains")]:
            self.assertEqual(search_guess(label)[0].label, expected, label)

    def test_pages(self):
        app = Appellation.objects.get(slug="tokaj")
        self.assertEqual(self.client.get(app.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(app.region.get_absolute_url()).status_code, 200)
        url = "/en" + self.hungarian().first().get_absolute_url()
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_blind_test(self):
        game = Game.objects.create(profile=WineProfile.objects.get(slug="tokaji-aszu"), max_attempts=8)
        self.assertEqual(engine.play(game, "Furmint").verdict, "hit")
        self.assertEqual(engine.play(game, "Tokaj-Hegyalja").verdict, "hit")

    def test_clues_never_name_the_answer(self):
        for lang in ("fr", "en"):
            with translation.override(lang):
                for p in self.hungarian().select_related("appellation__region"):
                    t = engine.Target.of(p)
                    text = tr(p.description) + " " + ", ".join(tr(x) for x in p.pairings)
                    masked = normalize(engine.mask_text(text, t))
                    for name in [t.appellation.name, t.region.name, "hongr", "hungar"] + [g.name for g in t.main_grapes]:
                        self.assertNotIn(normalize(name), masked, f"{lang} {p.slug} : « {name} » visible")
