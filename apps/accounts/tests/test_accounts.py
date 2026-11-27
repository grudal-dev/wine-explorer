from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import NewsletterSubscription
from apps.blindtest.models import Game
from apps.catalog.models import WineProfile


class AccountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())

    def test_signup_logs_in(self):
        r = self.client.post(reverse("accounts:signup"), {
            "username": "lucas", "email": "lucas@example.com",
            "password": "Un-Bon-Cru-2026", "adult": "on",
        })
        self.assertRedirects(r, reverse("accounts:profile"))
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 200)

    def test_duplicate_email_rejected(self):
        User.objects.create_user("a", "x@example.com", "pw-123456789")
        r = self.client.post(reverse("accounts:signup"), {
            "username": "b", "email": "X@example.com",
            "password": "Un-Bon-Cru-2026", "adult": "on",
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

    def test_todays_wine_is_hidden_until_the_visitor_finished_the_daily(self):
        """Les parties terminées des autres sur le vin du jour ne sont visibles qu'après son propre défi."""
        from django.utils import timezone
        from apps.blindtest import engine
        today = timezone.localdate()
        todays = engine.daily_profile(today)
        other = WineProfile.objects.exclude(pk=todays.pk).first()
        zoe = User.objects.create_user("zoe", "z@example.com", "Un-Bon-Cru-2026")
        daily = Game.objects.create(user=zoe, profile=todays, mode=Game.Mode.DAILY, day=today,
                                    status=Game.Status.WON, score=50)
        free_same_wine = Game.objects.create(user=zoe, profile=todays, status=Game.Status.WON)
        free_other = Game.objects.create(user=zoe, profile=other, status=Game.Status.WON)
        url = reverse("accounts:player", args=["zoe"])

        # visiteur qui n'a pas joué : ni liste, ni fiche des parties sur le vin du jour
        r = self.client.get(url)
        self.assertEqual([g.pk for g in r.context["games"]], [free_other.pk])
        self.assertEqual(self.client.get(daily.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(free_same_wine.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(free_other.get_absolute_url()).status_code, 200)

        # visiteur dont le défi du jour est en cours : toujours masqué
        ann = User.objects.create_user("ann", "a@example.com", "Un-Bon-Cru-2026")
        mine = Game.objects.create(user=ann, profile=todays, mode=Game.Mode.DAILY, day=today)
        self.client.login(username="ann", password="Un-Bon-Cru-2026")
        self.assertEqual(self.client.get(daily.get_absolute_url()).status_code, 404)

        # défi terminé (même abandonné) : tout est visible
        mine.status = Game.Status.LOST
        mine.save()
        self.assertEqual(len(self.client.get(url).context["games"]), 3)
        self.assertEqual(self.client.get(daily.get_absolute_url()).status_code, 200)

    def test_hotcold_history_is_shown_and_todays_secret_is_protected(self):
        """L'historique chaud-froid est public ; le vin mystère du jour n'est dévoilé qu'à ceux qui l'ont trouvé ou abandonné."""
        from datetime import timedelta
        from django.utils import timezone
        from apps.nose.models import HotColdResult
        today = timezone.localdate()
        old = today - timedelta(days=2)
        zoe = User.objects.create_user("zoe", "z@example.com", "Un-Bon-Cru-2026")
        ann = User.objects.create_user("ann", "a@example.com", "Un-Bon-Cru-2026")
        HotColdResult.objects.create(user=zoe, day=old, secret="chablis-blanc", outcome="won", guesses=4, score=91)
        HotColdResult.objects.create(user=zoe, day=today, secret="cote-rotie-rouge", outcome="won", guesses=2, score=97)
        url = reverse("accounts:player", args=["zoe"])

        # visiteur anonyme : seulement le passé
        r = self.client.get(url)
        self.assertEqual([x.day for x in r.context["hotcold_games"]], [old])
        self.assertContains(r, "Chablis")
        self.assertNotContains(r, "Côte-Rôtie")

        # connecté mais sans chaud-froid du jour : toujours masqué
        self.client.login(username="ann", password="Un-Bon-Cru-2026")
        self.assertEqual(len(self.client.get(url).context["hotcold_games"]), 1)

        # après son propre résultat du jour (même un abandon) : tout est visible
        HotColdResult.objects.create(user=ann, day=today, secret="cote-rotie-rouge", outcome="abandoned",
                                     guesses=1, score=0)
        r = self.client.get(url)
        self.assertEqual([x.day for x in r.context["hotcold_games"]], [today, old])
        self.assertContains(r, "Côte-Rôtie")

        # sa propre page montre toujours son historique
        self.assertEqual(len(self.client.get(reverse("accounts:profile")).context["hotcold_games"]), 1)

    def test_anonymous_visitor_who_finished_todays_hotcold_unlocks_it(self):
        from django.utils import timezone
        from apps.nose.models import HotColdResult
        today = timezone.localdate()
        zoe = User.objects.create_user("zoe", "z@example.com", "Un-Bon-Cru-2026")
        HotColdResult.objects.create(user=zoe, day=today, secret="cote-rotie-rouge", outcome="won", guesses=2, score=97)
        url = reverse("accounts:player", args=["zoe"])
        self.assertEqual(len(self.client.get(url).context["hotcold_games"]), 0)
        session = self.client.session
        session["hotcold"] = {"mode": "daily", "day": today.isoformat(), "secret": "cote-rotie-rouge",
                              "guesses": [], "over": "abandoned"}
        session.save()
        self.assertEqual(len(self.client.get(url).context["hotcold_games"]), 1)
        # une partie libre terminée ne débloque rien
        session["hotcold"] = {"mode": "free", "day": today.isoformat(), "secret": "x", "guesses": [], "over": "won"}
        session.save()
        self.assertEqual(len(self.client.get(url).context["hotcold_games"]), 0)

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
        # Le classement, c'est le blind test du jour ; le chaud-froid (bonus) a son tableau à part.
        r = self.client.get(reverse("accounts:ranking"))
        self.assertEqual(r.context["game"], "blindtest")
        self.assertEqual([(x["username"], x["points"]) for x in r.context["today"]], [("ann", 60)])
        hot = self.client.get(reverse("accounts:ranking") + "?jeu=hotcold")
        self.assertEqual([(x["username"], x["points"]) for x in hot.context["today"]], [("bob", 100), ("ann", 91)])
        # Le total reste calculé pour l'application mobile.
        from apps.accounts.rankings import standings
        total = standings("total", today)["today"]
        self.assertEqual([(x["username"], x["points"]) for x in total], [("ann", 151), ("bob", 100)])
        self.assertContains(hot, "bonus")
        bad = self.client.get(reverse("accounts:ranking") + "?jeu=zzz")
        self.assertEqual(bad.context["game"], "blindtest")

    def test_home_shows_daily_challenges_and_games_menu(self):
        home = self.client.get("/")
        self.assertContains(home, "Le vin du jour")
        self.assertContains(home, "Jouer le vin du jour")
        self.assertContains(home, 'data-deadline="')
        self.assertContains(home, 'class="nav-group"')
        self.assertEqual([c["state"] for c in home.context["daily"]["cards"]], ["todo", "todo"])
        User.objects.create_user("eve", "e@example.com", "Un-Bon-Cru-2026")
        self.client.login(username="eve", password="Un-Bon-Cru-2026")
        self.client.post(reverse("blindtest:start"), {"mode": "daily"})
        home = self.client.get("/")
        self.assertEqual(home.context["daily"]["cards"][0]["state"], "playing")


class NewsletterTests(TestCase):
    SIGNUP = {"username": "lucas", "email": "lucas@example.com",
              "password": "Un-Bon-Cru-2026", "adult": "on"}

    def test_signup_form_asks_and_is_unchecked(self):
        r = self.client.get(reverse("accounts:signup"))
        self.assertContains(r, 'name="newsletter"')
        self.assertNotContains(r, 'name="newsletter" checked')

    def test_signup_without_consent_does_not_subscribe(self):
        self.client.post(reverse("accounts:signup"), self.SIGNUP)
        self.assertFalse(NewsletterSubscription.objects.exists())

    def test_signup_with_consent_subscribes(self):
        self.client.post(reverse("accounts:signup"), {**self.SIGNUP, "newsletter": "on"})
        self.assertTrue(NewsletterSubscription.objects.get().is_active)

    def test_toggle_from_profile(self):
        self.client.post(reverse("accounts:signup"), self.SIGNUP)
        self.client.post(reverse("accounts:newsletter"), {"subscribe": "1"})
        self.assertTrue(NewsletterSubscription.objects.get().is_active)
        self.client.post(reverse("accounts:newsletter"), {})
        self.assertFalse(NewsletterSubscription.objects.get().is_active)

    def test_unsubscribe_link_needs_post(self):
        self.client.post(reverse("accounts:signup"), {**self.SIGNUP, "newsletter": "on"})
        sub = NewsletterSubscription.objects.get()
        url = reverse("accounts:newsletter_unsubscribe", args=[sub.token])
        self.assertEqual(self.client.get(url).status_code, 200)
        sub.refresh_from_db()
        self.assertTrue(sub.is_active)
        self.client.post(url)
        sub.refresh_from_db()
        self.assertFalse(sub.is_active)

    def test_send_only_to_active_subscribers(self):
        from django.core import mail
        import tempfile, os
        a = User.objects.create_user("a", "a@example.com", "pw-123456789")
        b = User.objects.create_user("b", "b@example.com", "pw-123456789")
        User.objects.create_user("c", "c@example.com", "pw-123456789")
        NewsletterSubscription.subscribe(a)
        NewsletterSubscription.subscribe(b)
        NewsletterSubscription.unsubscribe(b)
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Bonjour")
        try:
            call_command("send_newsletter", subject="Test", body_file=f.name, stdout=StringIO())
        finally:
            os.unlink(f.name)
        self.assertEqual([m.to for m in mail.outbox], [["a@example.com"]])
        self.assertIn("desinscription", mail.outbox[0].body)

    def test_signup_requires_adult_attestation(self):
        data = {k: v for k, v in self.SIGNUP.items() if k != "adult"}
        r = self.client.post(reverse("accounts:signup"), data)
        self.assertContains(r, "18 ans ou plus")
        self.assertFalse(User.objects.exists())
