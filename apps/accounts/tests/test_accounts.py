from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.blindtest.models import Game


class AccountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())

    def test_signup_logs_in(self):
        r = self.client.post(reverse("accounts:signup"), {
            "username": "lucas", "email": "lucas@example.com",
            "password1": "Un-Bon-Cru-2026", "password2": "Un-Bon-Cru-2026",
        })
        self.assertRedirects(r, reverse("accounts:profile"))
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 200)

    def test_duplicate_email_rejected(self):
        User.objects.create_user("a", "x@example.com", "pw-123456789")
        r = self.client.post(reverse("accounts:signup"), {
            "username": "b", "email": "X@example.com",
            "password1": "Un-Bon-Cru-2026", "password2": "Un-Bon-Cru-2026",
        })
        self.assertContains(r, "existe déjà")

    def test_login_claims_anonymous_games(self):
        User.objects.create_user("marie", "m@example.com", "Un-Bon-Cru-2026")
        self.client.post(reverse("blindtest:start"), {"mode": "free"})
        game = Game.objects.get()
        self.assertIsNone(game.user)
        self.client.post(reverse("accounts:login"), {"username": "marie", "password": "Un-Bon-Cru-2026"})
        game.refresh_from_db()
        self.assertEqual(game.user.username, "marie")
        self.assertEqual(self.client.get(game.get_absolute_url()).status_code, 200)

    def test_ranking_and_profile_require_login(self):
        self.assertEqual(self.client.get(reverse("accounts:ranking")).status_code, 200)
        r = self.client.get(reverse("accounts:profile"))
        self.assertEqual(r.status_code, 302)

    def test_all_time_ranking_ignores_free_games(self):
        from django.utils import timezone
        from apps.catalog.models import WineProfile
        user = User.objects.create_user("jo", "jo@example.com", "Un-Bon-Cru-2026")
        profile = WineProfile.objects.first()
        Game.objects.create(user=user, profile=profile, mode=Game.Mode.FREE,
                            status=Game.Status.WON, score=500)
        Game.objects.create(user=user, profile=profile, mode=Game.Mode.DAILY,
                            day=timezone.localdate(), status=Game.Status.WON, score=70)
        r = self.client.get(reverse("accounts:ranking") + "?jeu=blindtest")
        row = list(r.context["all_time"])[0]
        self.assertEqual((row["points"], row["played"]), (70, 1))

    def test_public_player_profile_hides_games_in_progress(self):
        from apps.catalog.models import WineProfile
        user = User.objects.create_user("zoe", "z@example.com", "Un-Bon-Cru-2026")
        profile = WineProfile.objects.first()
        Game.objects.create(user=user, profile=profile, status=Game.Status.WON, score=40)
        Game.objects.create(user=user, profile=WineProfile.objects.last(), status=Game.Status.PLAYING)
        r = self.client.get(reverse("accounts:player", args=["zoe"]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.context["games"]), 1)
        self.assertNotContains(r, "Partie en cours")
        self.assertNotContains(r, "z@example.com")
        self.assertEqual(self.client.get(reverse("accounts:player", args=["inconnu"])).status_code, 404)

    def test_own_player_url_redirects_to_profile(self):
        User.objects.create_user("zoe", "z@example.com", "Un-Bon-Cru-2026")
        self.client.login(username="zoe", password="Un-Bon-Cru-2026")
        self.assertRedirects(self.client.get(reverse("accounts:player", args=["zoe"])),
                             reverse("accounts:profile"))

    def test_total_ranking_adds_both_games(self):
        from django.utils import timezone
        from apps.catalog.models import WineProfile
        from apps.nose.models import HotColdResult
        today = timezone.localdate()
        profile = WineProfile.objects.first()
        ann = User.objects.create_user("ann", "a@example.com", "Un-Bon-Cru-2026")
        bob = User.objects.create_user("bob", "b@example.com", "Un-Bon-Cru-2026")
        Game.objects.create(user=ann, profile=profile, mode=Game.Mode.DAILY, day=today,
                            status=Game.Status.WON, score=60)
        HotColdResult.objects.create(user=ann, day=today, secret="x", outcome="won", guesses=4, score=91)
        HotColdResult.objects.create(user=bob, day=today, secret="x", outcome="won", guesses=1, score=100)
        Game.objects.create(user=bob, profile=profile, mode=Game.Mode.FREE, status=Game.Status.WON, score=999)
        r = self.client.get(reverse("accounts:ranking"))
        rows = list(r.context["today"])
        self.assertEqual([(x["username"], x["blindtest"], x["hotcold"], x["points"]) for x in rows],
                         [("ann", 60, 91, 151), ("bob", 0, 100, 100)])
        self.assertEqual(list(r.context["all_time"])[0]["points"], 151)
        self.assertContains(r, "Total des jeux")
        bad = self.client.get(reverse("accounts:ranking") + "?jeu=zzz")
        self.assertEqual(bad.context["game"], "total")

    def test_home_shows_daily_challenges_and_games_menu(self):
        home = self.client.get("/")
        self.assertContains(home, "Les défis du jour")
        self.assertContains(home, 'data-deadline="')
        self.assertContains(home, 'class="nav-group"')
        self.assertEqual([c["state"] for c in home.context["daily"]["cards"]], ["todo", "todo"])
        User.objects.create_user("eve", "e@example.com", "Un-Bon-Cru-2026")
        self.client.login(username="eve", password="Un-Bon-Cru-2026")
        self.client.post(reverse("blindtest:start"), {"mode": "daily"})
        home = self.client.get("/")
        self.assertEqual(home.context["daily"]["cards"][0]["state"], "playing")
