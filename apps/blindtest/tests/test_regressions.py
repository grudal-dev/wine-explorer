"""Régressions relevées lors de l'audit du 11/11/2026."""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.blindtest import engine
from apps.blindtest.models import Game
from apps.catalog.models import Appellation, WineProfile
from apps.catalog.text import normalize


@override_settings(BLINDTEST_MAX_ATTEMPTS=8)
class AttemptLimitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())
        cls.profile = WineProfile.objects.get(slug="ajaccio-rouge")  # deux cépages principaux

    def test_a_hit_on_the_last_attempt_still_ends_the_game(self):
        """Un « trouvé » au dernier essai ne doit pas offrir d'essais supplémentaires."""
        game = Game.objects.create(profile=self.profile, max_attempts=8)
        target = engine.Target.of(self.profile)
        wrong = Appellation.objects.exclude(region__in=[target.region.id]).exclude(
            region__parent=target.region)[:7]
        for app in wrong:
            engine.play(game, "", f"appellation:{app.id}")
        engine.play(game, "", f"grape:{target.main_grapes[0].id}")
        game.refresh_from_db()
        self.assertEqual(game.attempts_used, 8)
        self.assertEqual(game.status, Game.Status.LOST)
        with self.assertRaises(engine.GuessError):
            engine.play(game, "", f"grape:{target.main_grapes[1].id}")

    def test_winning_on_the_last_attempt_is_a_win(self):
        profile = WineProfile.objects.get(slug="chablis-blanc")
        game = Game.objects.create(profile=profile, max_attempts=2)
        engine.play(game, "chardonnay")
        engine.play(game, "chablis")
        game.refresh_from_db()
        self.assertEqual(game.status, Game.Status.WON)

    def test_no_game_can_exceed_its_quota(self):
        for profile in WineProfile.objects.all()[:25]:
            game = Game.objects.create(profile=profile, max_attempts=3)
            for app in Appellation.objects.exclude(pk=profile.appellation_id)[:6]:
                try:
                    engine.play(game, "", f"appellation:{app.id}")
                except engine.GuessError:
                    break
            game.refresh_from_db()
            self.assertLessEqual(game.attempts_used, 3, profile.slug)
            self.assertTrue(game.is_over, profile.slug)


class MaskingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())

    def test_clues_never_name_the_answer(self):
        """Ni le commentaire ni les accords ne citent l'appellation, la région ou leurs dérivés."""
        for p in WineProfile.objects.select_related("appellation__region__parent"):
            t = engine.Target.of(p)
            text = normalize(engine.mask_text(p.description + " " + ", ".join(p.pairings), t))
            names = [t.appellation.name, t.region.name] + [g.name for g in t.main_grapes]
            for name in names:
                self.assertNotIn(normalize(name), text, f"{p.slug} : « {name} » visible")

    def test_derived_words_are_masked(self):
        cases = {
            "arbois-rouge": "jurassien", "pic-saint-loup-rouge": "languedocien",
            "macon-villages-blanc": "bourguignon", "morgon-rouge": "morgonne",
            "cremant-dalsace-blanc": "alsacien",
        }
        for slug, word in cases.items():
            p = WineProfile.objects.get(slug=slug)
            self.assertNotIn(word, normalize(engine.mask_text(p.description, engine.Target.of(p))), slug)

    def test_common_words_survive(self):
        p = WineProfile.objects.get(slug="cote-rotie-rouge")
        self.assertIn("coteaux", engine.mask_text(p.description, engine.Target.of(p)))

    def test_pairings_are_masked_while_playing_only(self):
        p = WineProfile.objects.get(slug="patrimonio-rouge")
        game = Game.objects.create(profile=p, max_attempts=8, clues_revealed=len(engine.CLUES))
        body = next(c["body"] for c in engine.tasting_sheet(game)["clues"] if c["key"] == "pairings")
        self.assertNotIn("corse", normalize(body))
        game.status = Game.Status.ABANDONED
        body = next(c["body"] for c in engine.tasting_sheet(game)["clues"] if c["key"] == "pairings")
        self.assertIn("corse", normalize(body))


class FreeTextTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())

    def test_normalize(self):
        self.assertEqual(normalize("Œillade"), "oeillade")
        self.assertEqual(normalize("St-Émilion"), "saint emilion")
        self.assertEqual(normalize("Côte-Rôtie"), "cote rotie")

    def test_abbreviation_and_typos_resolve(self):
        self.assertEqual(engine.search_guess("st emilion")[0].label, "Saint-Émilion Grand Cru")
        game = Game.objects.create(profile=WineProfile.objects.get(slug="chablis-blanc"), max_attempts=8)
        self.assertEqual(engine.play(game, "sirah").label, "Syrah")
        with self.assertRaises(engine.GuessError):
            engine.play(game, "xyzzy")
