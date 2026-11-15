"""API des applications mobiles : comptes, défis du jour, anti-spoiler, rattachement des parties."""

from io import StringIO

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.blindtest import engine
from apps.blindtest.models import Game
from apps.nose.models import HotColdResult

DEVICE = "0b6c7a1e-1d2f-4c3b-9a8e-123456789abc"
PASSWORD = "Un-Bon-Cru-2026"


class ApiTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())

    def setUp(self):
        cache.clear()  # limites de débit
        self.api = APIClient(HTTP_X_DEVICE_ID=DEVICE, HTTP_ACCEPT_LANGUAGE="fr")

    def as_user(self, username: str) -> tuple[User, APIClient]:
        user = User.objects.create_user(username, f"{username}@example.com", PASSWORD)
        client = APIClient(HTTP_ACCEPT_LANGUAGE="fr")
        token = client.post("/api/v1/auth/login/", {"username": username, "password": PASSWORD},
                            format="json").json()["token"]
        client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        return user, client


class AccountTests(ApiTestCase):
    def test_signup_requires_adult_and_returns_a_token(self):
        payload = {"username": "lea", "email": "lea@example.com", "password": PASSWORD}
        r = self.api.post("/api/v1/auth/signup/", payload, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("adult", r.json()["errors"])
        r = self.api.post("/api/v1/auth/signup/", {**payload, "adult": True}, format="json")
        self.assertEqual(r.status_code, 201)
        self.api.credentials(HTTP_AUTHORIZATION=f"Token {r.json()['token']}")
        self.assertEqual(self.api.get("/api/v1/me/").json()["user"]["username"], "lea")

    def test_login_by_email_logout_and_bad_password(self):
        User.objects.create_user("max", "max@example.com", PASSWORD)
        self.assertEqual(self.api.post("/api/v1/auth/login/", {"username": "max", "password": "x"},
                                       format="json").status_code, 401)
        r = self.api.post("/api/v1/auth/login/", {"username": "MAX@example.com", "password": PASSWORD},
                          format="json")
        self.assertEqual(r.status_code, 200)
        self.api.credentials(HTTP_AUTHORIZATION=f"Token {r.json()['token']}")
        self.assertEqual(self.api.post("/api/v1/auth/logout/").status_code, 204)
        self.assertEqual(self.api.get("/api/v1/me/").status_code, 401)

    def test_account_deletion_needs_the_password(self):
        user, client = self.as_user("sam")
        self.assertEqual(client.delete("/api/v1/me/", {"password": "non"}, format="json").status_code, 403)
        self.assertEqual(client.delete("/api/v1/me/", {"password": PASSWORD}, format="json").status_code, 204)
        self.assertFalse(User.objects.filter(pk=user.pk).exists())

    def test_device_games_join_the_account_at_login(self):
        game = self.api.post("/api/v1/blindtest/games/", {"mode": "free"}, format="json").json()
        self.api.post("/api/v1/hotcold/give-up/")
        User.objects.create_user("noe", "noe@example.com", PASSWORD)
        self.api.post("/api/v1/auth/login/", {"username": "noe", "password": PASSWORD}, format="json")
        noe = User.objects.get(username="noe")
        self.assertTrue(Game.objects.filter(public_id=game["id"], user=noe).exists())
        self.assertTrue(HotColdResult.objects.filter(user=noe, day=timezone.localdate()).exists())


class BlindTestTests(ApiTestCase):
    def test_play_a_daily_game_until_the_end(self):
        r = self.api.post("/api/v1/blindtest/games/", {"mode": "daily"}, format="json")
        self.assertEqual(r.status_code, 201)
        game = r.json()
        self.assertTrue(game["is_owner"])
        self.assertIsNone(game["wine"])  # pas de réponse avant la fin
        self.assertTrue(all(s["answer"] is None for s in game["sheet"]["slots"]))
        # même défi du jour au second appel
        again = self.api.post("/api/v1/blindtest/games/", {"mode": "daily"}, format="json").json()
        self.assertEqual(again["id"], game["id"])
        self.assertEqual(self.api.get("/api/v1/today/").json()["blindtest"]["state"], "playing")

        bad = self.api.post(f"/api/v1/blindtest/games/{game['id']}/guess/", {"q": "zzzzzz"}, format="json")
        self.assertEqual(bad.status_code, 400)
        done = self.api.post(f"/api/v1/blindtest/games/{game['id']}/give-up/").json()
        self.assertTrue(done["is_over"])
        self.assertEqual(done["wine"]["slug"], engine.daily_profile(timezone.localdate()).slug)
        self.assertEqual(self.api.get("/api/v1/today/").json()["blindtest"]["state"], "done")

    def test_a_guess_is_scored(self):
        game = self.api.post("/api/v1/blindtest/games/", {"mode": "free"}, format="json").json()
        r = self.api.post(f"/api/v1/blindtest/games/{game['id']}/guess/", {"q": "chardonnay"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["guesses"]), 1)
        self.assertIn(r.json()["guesses"][0]["verdict"], {"hit", "close", "miss", "info"})

    def test_someone_elses_games_follow_the_spoiler_rules(self):
        today = timezone.localdate()
        zoe = User.objects.create_user("zoe", "z@example.com", PASSWORD)
        daily = Game.objects.create(user=zoe, profile=engine.daily_profile(today), mode="daily", day=today,
                                    status="won", score=500)
        playing = Game.objects.create(user=zoe, profile=engine.random_profile(), mode="free")
        stranger = APIClient(HTTP_X_DEVICE_ID="ffffffff-0000-4000-8000-000000000000")
        self.assertEqual(stranger.get(f"/api/v1/blindtest/games/{daily.public_id}/").status_code, 404)
        self.assertEqual(stranger.get(f"/api/v1/blindtest/games/{playing.public_id}/").status_code, 404)
        self.assertEqual(stranger.get("/api/v1/players/zoe/").json()["games"], [])
        game = stranger.post("/api/v1/blindtest/games/", {"mode": "daily"}, format="json").json()
        stranger.post(f"/api/v1/blindtest/games/{game['id']}/give-up/")
        r = stranger.get(f"/api/v1/blindtest/games/{daily.public_id}/")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["is_owner"])
        self.assertEqual(stranger.post(f"/api/v1/blindtest/games/{daily.public_id}/guess/",
                                       {"q": "x"}, format="json").status_code, 403)

    def test_a_device_id_is_required_without_an_account(self):
        r = APIClient().post("/api/v1/blindtest/games/", {"mode": "free"}, format="json")
        self.assertEqual(r.status_code, 400)


class HotColdTests(ApiTestCase):
    def test_daily_game_is_kept_on_the_server(self):
        board = self.api.get("/api/v1/hotcold/").json()
        self.assertEqual((board["mode"], board["count"]), ("daily", 0))
        self.assertNotIn("answer", board)  # le vin mystère ne quitte pas le serveur
        r = self.api.post("/api/v1/hotcold/guess/", {"q": "syrah"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["count"], 1)
        self.assertEqual(self.api.post("/api/v1/hotcold/guess/", {"q": "syrah"}, format="json").status_code, 400)
        self.assertEqual(self.api.get("/api/v1/hotcold/").json()["count"], 1)  # repris tel quel
        self.assertEqual(self.api.get("/api/v1/today/").json()["hotcold"]["state"], "playing")
        over = self.api.post("/api/v1/hotcold/give-up/").json()
        self.assertEqual(over["over"], "abandoned")
        self.assertIn("answer", over)

    def test_free_game_then_back_to_the_daily(self):
        self.api.post("/api/v1/hotcold/guess/", {"q": "syrah"}, format="json")
        free = self.api.post("/api/v1/hotcold/new/", {"mode": "free"}, format="json").json()
        self.assertEqual((free["mode"], free["count"]), ("free", 0))
        daily = self.api.post("/api/v1/hotcold/new/", {"mode": "daily"}, format="json").json()
        self.assertEqual((daily["mode"], daily["count"]), ("daily", 1))

    def test_ranked_result_for_a_signed_in_player(self):
        user, client = self.as_user("ivy")
        r = client.post("/api/v1/hotcold/give-up/").json()
        self.assertEqual(r["ranked"], {"score": 0, "guesses": 0})
        self.assertTrue(HotColdResult.objects.filter(user=user).exists())

    def test_history_hides_todays_secret_until_finished(self):
        today = timezone.localdate()
        zoe = User.objects.create_user("zoe", "z@example.com", PASSWORD)
        HotColdResult.objects.create(user=zoe, day=today, secret="cote-rotie-rouge", outcome="won",
                                     guesses=2, score=97)
        self.assertEqual(self.api.get("/api/v1/players/zoe/").json()["hotcold"], [])
        self.api.post("/api/v1/hotcold/give-up/")
        self.assertEqual(len(self.api.get("/api/v1/players/zoe/").json()["hotcold"]), 1)

    def test_suggestions(self):
        r = self.api.get("/api/v1/hotcold/suggest/", {"q": "syr"}).json()["results"]
        self.assertTrue(any(x["label"].lower().startswith("syrah") for x in r))


class PublicDataTests(ApiTestCase):
    def test_rankings_wines_and_english(self):
        self.assertEqual(self.api.get("/api/v1/rankings/", {"game": "hotcold"}).json()["game"], "hotcold")
        self.assertEqual(self.api.get("/api/v1/rankings/", {"game": "zzz"}).json()["game"], "total")
        wine = self.api.get("/api/v1/wines/chablis-blanc/").json()
        self.assertEqual(wine["appellation"], "Chablis")
        self.assertTrue(wine["grapes"])
        en = APIClient(HTTP_ACCEPT_LANGUAGE="en").get("/api/v1/wines/chablis-blanc/").json()
        self.assertEqual(en["color_label"], "White")
        self.assertTrue(self.api.get("/api/v1/wines/", {"q": "chab"}).json()["results"])
