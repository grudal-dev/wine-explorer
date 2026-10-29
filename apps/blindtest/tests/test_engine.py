from datetime import date
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.blindtest import engine
from apps.blindtest.models import Game
from apps.catalog.models import WineProfile


@override_settings(BLINDTEST_MAX_ATTEMPTS=8)
class EngineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())
        cls.chablis = WineProfile.objects.get(slug="chablis-blanc")
        cls.cdp = WineProfile.objects.get(slug="chateauneuf-du-pape-rouge")

    def game(self, profile):
        return Game.objects.create(profile=profile, max_attempts=8)

    def test_full_win(self):
        g = self.game(self.chablis)
        self.assertEqual(engine.play(g, "Bourgogne").verdict, "hit")
        self.assertEqual(engine.play(g, "chablis").verdict, "hit")
        g.refresh_from_db()
        self.assertEqual(g.status, Game.Status.PLAYING)  # reste le cépage
        engine.play(g, "chardonnay")
        g.refresh_from_db()
        self.assertEqual(g.status, Game.Status.WON)
        self.assertEqual(g.score, 1000 - 90 * 2)
        self.assertEqual(g.clues_revealed, 0)

    def test_misses_reveal_clues_and_lose(self):
        g = self.game(self.chablis)
        for term in ["Alsace", "Bordeaux", "Provence", "Corse", "Jura", "Savoie", "Champagne", "Sud-Ouest"]:
            engine.play(g, term)
        g.refresh_from_db()
        self.assertEqual(g.status, Game.Status.LOST)
        self.assertEqual(g.clues_revealed, len(engine.CLUES))
        with self.assertRaises(engine.GuessError):
            engine.play(g, "Chablis")

    def test_distance_feedback(self):
        g = self.game(self.chablis)
        guess = engine.play(g, "Pauillac")
        self.assertEqual(guess.verdict, "miss")
        self.assertIn("km", guess.feedback)
        self.assertIn("nord-est", guess.feedback)

    def test_close_and_minor_grape(self):
        g = self.game(self.cdp)
        self.assertEqual(engine.play(g, "Gigondas").verdict, "close")
        g.refresh_from_db()
        self.assertTrue(g.found.get("region"))
        self.assertEqual(engine.play(g, "Cinsault").verdict, "close")  # 5 %
        self.assertEqual(engine.play(g, "Grenache").verdict, "hit")

    def test_color_guess_not_counted_and_duplicates_rejected(self):
        g = self.game(self.chablis)
        guess = engine.play(g, "blanc")
        self.assertFalse(guess.counted)
        engine.play(g, "Alsace")
        with self.assertRaises(engine.GuessError):
            engine.play(g, "alsace")
        with self.assertRaises(engine.GuessError):
            engine.play(g, "zzzzqqq")
        self.assertEqual(g.attempts_used, 1)

    def test_choice_disambiguates(self):
        g = self.game(self.chablis)
        app = self.chablis.appellation
        guess = engine.play(g, "", f"appellation:{app.id}")
        self.assertEqual(guess.verdict, "hit")

    def test_mask_hides_names(self):
        t = engine.Target.of(self.cdp)
        masked = engine.mask_text("Le Grenache et la Syrah de Châteauneuf-du-Pape, en Vallée du Rhône", t)
        for word in ["Grenache", "Syrah", "Châteauneuf", "Rhône"]:
            self.assertNotIn(word, masked)

    def test_sheet_hides_answers_until_over(self):
        g = self.game(self.chablis)
        sheet = engine.tasting_sheet(g)
        self.assertTrue(all(not s["show"] for s in sheet["slots"]))
        self.assertEqual(len(sheet["aromas"]), engine.AROMAS_START)
        engine.abandon(g)
        sheet = engine.tasting_sheet(g)
        self.assertTrue(all(s["show"] for s in sheet["slots"]))

    def test_daily_is_deterministic(self):
        d = date(2026, 10, 29)
        self.assertEqual(engine.daily_profile(d), engine.daily_profile(d))

    def test_one_daily_per_user(self):
        u = User.objects.create_user("lea", password="x-pass-123")
        a = engine.new_game(mode="daily", user=u)
        b = engine.new_game(mode="daily", user=u)
        self.assertEqual(a.pk, b.pk)


class ViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())

    def start(self, client, mode="free"):
        r = client.post(reverse("blindtest:start"), {"mode": mode})
        self.assertEqual(r.status_code, 302)
        return Game.objects.latest("created_at")

    def test_flow_htmx(self):
        self.assertEqual(self.client.get(reverse("blindtest:home")).status_code, 200)
        game = self.start(self.client)
        page = self.client.get(game.get_absolute_url())
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, game.profile.appellation.name + "</p>")
        r = self.client.post(reverse("blindtest:guess", args=[game.public_id]), {"q": "Bourgogne"},
                             HTTP_HX_REQUEST="true")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'id="board"')
        self.assertEqual(game.guesses.count(), 1)

    def test_other_session_cannot_play(self):
        game = self.start(self.client)
        other = self.client_class()
        self.assertEqual(other.get(game.get_absolute_url()).status_code, 404)
        r = other.post(reverse("blindtest:guess", args=[game.public_id]), {"q": "Alsace"})
        self.assertEqual(r.status_code, 404)

    def test_finished_game_is_shareable(self):
        game = self.start(self.client)
        self.client.post(reverse("blindtest:give_up", args=[game.public_id]))
        other = self.client_class()
        r = other.get(game.get_absolute_url())
        self.assertContains(r, game.profile.appellation.name)
        self.assertNotContains(r, "guess-input")

    def test_suggest(self):
        r = self.client.get(reverse("blindtest:suggest"), {"q": "gewu"})
        self.assertEqual(r.json()["results"][0]["label"], "Gewurztraminer")
