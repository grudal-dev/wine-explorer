from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import translation

from apps.blindtest import engine
from apps.blindtest.models import Game
from apps.catalog.i18n import tr
from apps.catalog.index import search_guess
from apps.catalog.models import Appellation, Country, Region, WineProfile
from apps.catalog.text import normalize
from apps.molecules.models import ProfileMolecule


class ItalyTests(TestCase):
    """Le jeu de données italien se charge à côté du français et reste cohérent."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", country="all", stdout=StringIO())

    def italian(self):
        return WineProfile.objects.filter(appellation__country__code="IT")

    def test_loaded_next_to_france(self):
        self.assertEqual(Country.objects.filter(code__in=["FR", "IT"]).count(), 2)
        self.assertGreaterEqual(self.italian().count(), 30)
        self.assertTrue(WineProfile.objects.filter(appellation__country__code="FR").exists())

    def test_profiles_are_consistent(self):
        for p in self.italian().prefetch_related("profile_grapes", "profile_aromas"):
            self.assertEqual(sum(pg.share for pg in p.profile_grapes.all()), 100, p.name)
            self.assertGreaterEqual(p.profile_aromas.count(), 4, p.name)

    def test_load_is_idempotent(self):
        before = (WineProfile.objects.count(), Region.objects.count(), Appellation.objects.count())
        call_command("load_seed", country="all", stdout=StringIO())
        self.assertEqual(before, (WineProfile.objects.count(), Region.objects.count(), Appellation.objects.count()))

    def test_every_wine_has_molecules(self):
        for p in self.italian():
            self.assertTrue(ProfileMolecule.objects.filter(profile=p).exists(), p.name)

    def test_grape_aliases_resolve(self):
        for label, expected in [("Cannonau", "Grenache"), ("Pinot Nero", "Pinot Noir"), ("Moscato", "Muscat à petits grains"),
                                ("Prosecco", "Glera"), ("Shiraz", "Syrah")]:
            self.assertEqual(search_guess(label)[0].label, expected, label)

    def test_pages(self):
        app = Appellation.objects.get(slug="barolo")
        self.assertEqual(self.client.get(app.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(app.region.root.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(self.italian().first().get_absolute_url()).status_code, 200)

    def test_blind_test_on_an_italian_wine(self):
        profile = WineProfile.objects.get(slug="barolo-rouge")
        game = Game.objects.create(profile=profile, max_attempts=8)
        self.assertEqual(engine.play(game, "Piémont").verdict, "hit")
        self.assertNotEqual(engine.play(game, "Toscane").verdict, "hit")

    def test_english_clues_never_name_the_answer(self):
        with translation.override("en"):
            for p in self.italian().select_related("appellation__region__parent"):
                t = engine.Target.of(p)
                text = tr(p.description) + " " + ", ".join(tr(x) for x in p.pairings)
                masked = normalize(engine.mask_text(text, t))
                names = [t.appellation.name, t.region.name, tr(t.region.name)] + [g.name for g in t.main_grapes]
                for name in names:
                    self.assertNotIn(normalize(name), masked, f"{p.slug} : « {name} » visible")
