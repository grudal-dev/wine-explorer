"""« Bloqué ? » : la carte des goûts proposée en cours de partie, sans trahir le vin."""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.blindtest import engine
from apps.blindtest.models import Game
from apps.blindtest.views import STUCK_AFTER
from apps.catalog.models import Appellation


class StuckHintTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())

    def start(self) -> Game:
        self.client.post(reverse("blindtest:start"), {"mode": "free"})
        return Game.objects.latest("created_at")

    def test_map_appears_once_stuck_and_never_points_to_the_answer(self):
        game = self.start()
        self.assertNotContains(self.client.get(game.get_absolute_url()), "Bloqué ?")
        wrong = Appellation.objects.exclude(pk=game.profile.appellation_id).filter(profiles__isnull=False).distinct()
        for app in wrong[:STUCK_AFTER]:
            engine.play(game, "", f"appellation:{app.id}")
        page = self.client.get(game.get_absolute_url())
        self.assertContains(page, "Bloqué ?")
        self.assertContains(page, reverse("embeddings:map") + "?focus=profile:")
        self.assertNotContains(page, f"focus=profile:{game.profile.slug}")

    def test_hint_leaves_once_the_game_is_over(self):
        game = self.start()
        wrong = Appellation.objects.exclude(pk=game.profile.appellation_id)
        for app in wrong[:STUCK_AFTER]:
            engine.play(game, "", f"appellation:{app.id}")
        self.client.post(reverse("blindtest:give_up", args=[game.public_id]))
        self.assertNotContains(self.client.get(game.get_absolute_url()), "Bloqué ?")
