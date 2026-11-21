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


class PortugalTests(TestCase):
    """Le porto (data/pt/) se charge à côté des autres pays."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", country="all", stdout=StringIO())

    def tearDown(self):
        translation.activate("fr")

    def portuguese(self):
        return WineProfile.objects.filter(appellation__country__code="PT")

    def test_port_profiles(self):
        self.assertEqual(
            sorted(self.portuguese().values_list("slug", flat=True)),
            ["porto-blanc", "porto-colheita", "porto-late-bottled-vintage", "porto-rose", "porto-ruby",
             "porto-tawny-10-ans", "porto-vintage"],
        )
        for p in self.portuguese().prefetch_related("profile_grapes"):
            self.assertEqual(p.style, "mute", p.name)
            self.assertEqual(sum(pg.share for pg in p.profile_grapes.all()), 100, p.name)
            self.assertTrue(ProfileMolecule.objects.filter(profile=p).exists(), p.name)

    def test_guesses_resolve(self):
        for label, expected in [("Touriga Nacional", "Touriga Nacional"), ("Aragonez", "Tinta Roriz"),
                                ("Trincadeira", "Tinta Amarela"), ("Douro", "Douro")]:
            self.assertEqual(search_guess(label)[0].label, expected, label)

    def test_pages(self):
        app = Appellation.objects.get(slug="porto")
        self.assertEqual(self.client.get(app.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(app.region.get_absolute_url()).status_code, 200)
        url = "/en" + self.portuguese().first().get_absolute_url()
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_blind_test(self):
        game = Game.objects.create(profile=WineProfile.objects.get(slug="porto-ruby"), max_attempts=8)
        self.assertEqual(engine.play(game, "Touriga Franca").verdict, "hit")
        self.assertEqual(engine.play(game, "Douro").verdict, "hit")

    def test_clues_never_name_the_answer(self):
        for lang in ("fr", "en"):
            with translation.override(lang):
                for p in self.portuguese().select_related("appellation__region"):
                    t = engine.Target.of(p)
                    text = tr(p.description) + " " + ", ".join(tr(x) for x in p.pairings)
                    masked = normalize(engine.mask_text(text, t))
                    for name in [t.appellation.name, t.region.name, "portug"] + [g.name for g in t.main_grapes]:
                        self.assertNotIn(normalize(name), masked, f"{lang} {p.slug} : « {name} » visible")
