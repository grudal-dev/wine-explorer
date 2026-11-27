from datetime import date, timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.blindtest import engine, share
from apps.blindtest.models import Game
from apps.catalog.models import WineProfile


class ShareTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())

    def test_streak(self):
        today = date(2026, 11, 27)
        days = [today - timedelta(days=i) for i in (0, 1, 2, 4)]
        self.assertEqual(share.streak(days, today), 3)
        # Aujourd'hui pas encore joué : la série d'hier tient toujours.
        self.assertEqual(share.streak(days[1:], today), 2)
        self.assertEqual(share.streak([], today), 0)

    def test_text_never_names_the_wine(self):
        profile = WineProfile.objects.get(slug="chablis-blanc")
        game = Game.objects.create(profile=profile, max_attempts=8, mode=Game.Mode.DAILY, day=date(2026, 11, 27))
        engine.play(game, "Alsace")
        engine.play(game, "Chablis")
        game.refresh_from_db()
        text = share.text(game, "https://exemple.fr/blind-test/")
        self.assertIn("n° 88 · 2/8", text)
        self.assertIn("🟥🟩", text)
        self.assertNotIn("Chablis", text)

    def test_end_of_game_offers_share_and_keep_points(self):
        self.client.post(reverse("blindtest:start"), {"mode": "daily"})
        game = Game.objects.get()
        target = game.profile.appellation.name
        self.client.post(reverse("blindtest:guess", args=[game.public_id]), {"q": target})
        game.refresh_from_db()
        if not game.is_over:
            for g in game.profile.main_grapes():
                self.client.post(reverse("blindtest:guess", args=[game.public_id]), {"q": g.name})
        game.refresh_from_db()
        html = self.client.get(game.get_absolute_url()).content.decode()
        self.assertIn("data-share", html)
        if game.score > 0:
            self.assertIn("Gardez vos", html)

    def test_no_keep_points_for_zero(self):
        self.client.post(reverse("blindtest:start"), {"mode": "daily"})
        game = Game.objects.get()
        self.client.post(reverse("blindtest:give_up", args=[game.public_id]))
        html = self.client.get(game.get_absolute_url()).content.decode()
        self.assertIn("data-share", html)
        self.assertNotIn("Gardez vos 0", html)
