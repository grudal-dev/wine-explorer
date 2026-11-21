from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils.text import slugify

from apps.blindtest import engine
from apps.blindtest.models import Game, Guess
from apps.catalog import twins
from apps.catalog.models import Appellation, WineProfile


class TwinTests(TestCase):
    """Appellations jumelles au verre : l'une est acceptée pour l'autre (data/jumelles.yaml)."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", country="all", stdout=StringIO())

    def game(self, slug):
        return Game.objects.create(profile=WineProfile.objects.get(slug=slug), max_attempts=8)

    def test_every_twin_exists(self):
        known = set(Appellation.objects.values_list("slug", flat=True))
        self.assertEqual(set(twins.groups()) - known, set())

    def test_fleurie_counts_for_chiroubles(self):
        game = self.game("chiroubles-rouge")
        guess = engine.play(game, "Fleurie")
        self.assertEqual(guess.verdict, Guess.Verdict.HIT)
        self.assertIn("Chiroubles", guess.feedback)
        game.refresh_from_db()
        self.assertTrue(game.found["appellation"])
        engine.play(game, "Gamay")
        game.refresh_from_db()
        self.assertEqual(game.status, Game.Status.WON)

    def test_other_family_is_only_close(self):
        guess = engine.play(self.game("chiroubles-rouge"), "Morgon")
        self.assertEqual(guess.verdict, Guess.Verdict.CLOSE)

    def test_twin_must_make_that_colour(self):
        """Sancerre rouge : Pouilly-Fumé ne fait que du blanc, il n'est pas accepté."""
        rouge = WineProfile.objects.filter(appellation__slug="sancerre", color="rouge").first()
        guess = engine.play(Game.objects.create(profile=rouge, max_attempts=8), "Pouilly-Fumé")
        self.assertNotEqual(guess.verdict, Guess.Verdict.HIT)
        blanc = WineProfile.objects.filter(appellation__slug="sancerre", color="blanc").first()
        guess = engine.play(Game.objects.create(profile=blanc, max_attempts=8), "Pouilly-Fumé")
        self.assertEqual(guess.verdict, Guess.Verdict.HIT)

    def test_groups_are_symmetric(self):
        self.assertTrue(twins.are_twins(slugify("Côte de Brouilly"), "brouilly"))
        self.assertTrue(twins.are_twins("brouilly", slugify("Côte de Brouilly")))
        self.assertFalse(twins.are_twins("fleurie", "fleurie"))
