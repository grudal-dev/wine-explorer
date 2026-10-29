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
