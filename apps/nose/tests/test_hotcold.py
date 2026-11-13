from datetime import date
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import Aroma
from apps.embeddings.space import space
from apps.nose import hotcold, predictor
from apps.nose.models import HotColdResult


class HotColdEngineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())

    def setUp(self):
        self.sp = space()
        self.state = {"mode": "free", "day": "2026-11-11", "secret": "cote-rotie-rouge", "guesses": [], "over": ""}

    def test_daily_secret_is_stable_and_differs_from_other_days(self):
        a = hotcold.daily_secret(date(2026, 11, 11), self.sp)
        self.assertEqual(a, hotcold.daily_secret(date(2026, 11, 11), self.sp))
        days = {hotcold.daily_secret(date(2026, 11, d), self.sp) for d in range(1, 29)}
        self.assertGreater(len(days), 15)

    def test_temperature_orders_guesses(self):
        hot = hotcold.play(self.state, "syrah", "", self.sp)
        cold = hotcold.play(self.state, "chardonnay", "", self.sp)
        self.assertEqual(hot["id"], "grape:syrah")
        self.assertGreater(hot["temperature"], cold["temperature"])
        self.assertLess(hot["rank"], cold["rank"])
        self.assertFalse(self.state["over"])
        board = hotcold.board(self.state, self.sp)
        self.assertEqual([r["id"] for r in board["rows"]], ["grape:syrah", "grape:chardonnay"])
        self.assertEqual(board["last"]["id"], "grape:chardonnay")
        self.assertNotIn("answer", board)  # la solution ne sort pas avant la fin

    def test_close_wine_is_burning_and_secret_wins(self):
        near = hotcold.play(self.state, "", "profile:hermitage-rouge", self.sp)
        self.assertEqual(near["emoji"], "😱")
        self.assertLessEqual(near["rank"], 5)
        win = hotcold.play(self.state, "Côte-Rôtie rouge", "", self.sp)
        self.assertTrue(win["found"])
        self.assertEqual(self.state["over"], "won")
        board = hotcold.board(self.state, self.sp)
        self.assertEqual(board["answer"]["id"], "profile:cote-rotie-rouge")
        self.assertEqual(len(board["closest"]), 15)
        with self.assertRaises(hotcold.HotColdError):
            hotcold.play(self.state, "syrah", "", self.sp)

    def test_errors(self):
        with self.assertRaises(hotcold.HotColdError):
            hotcold.play(self.state, "", "", self.sp)
        with self.assertRaises(hotcold.HotColdError):
            hotcold.play(self.state, "xyzzy", "", self.sp)
        hotcold.play(self.state, "syrah", "", self.sp)
        with self.assertRaises(hotcold.HotColdError):
            hotcold.play(self.state, "Syrah", "", self.sp)
        self.assertEqual(self.state["guesses"], ["grape:syrah"])

    def test_typed_aroma_wins_over_homonymous_appellation(self):
        self.assertEqual(hotcold.resolve("cassis", "", self.sp), "aroma:cassis")


class HotColdViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())

    def test_flow(self):
        page = self.client.get(reverse("hotcold:game"))
        self.assertContains(page, "Chaud-froid")
        secret = self.client.session[hotcold.SESSION_KEY]["secret"]
        self.assertNotContains(page, secret)
        r = self.client.post(reverse("hotcold:guess"), {"q": "syrah"}, HTTP_HX_REQUEST="true")
        self.assertContains(r, 'id="hotcold"')
        self.assertContains(r, "Syrah")
        self.assertNotContains(r, secret)
        r = self.client.post(reverse("hotcold:guess"), {"q": "zzzz"}, HTTP_HX_REQUEST="true")
        self.assertContains(r, "pas dans le graphe")
        self.assertEqual(self.client.session[hotcold.SESSION_KEY]["guesses"], ["grape:syrah"])
        self.client.post(reverse("hotcold:give_up"))
        page = self.client.get(reverse("hotcold:game"))
        self.assertContains(page, "Partie abandonnée")
        self.assertContains(page, f"/catalogue/vins/{secret}/")
        self.client.post(reverse("hotcold:new"), {"mode": "free"})
        state = self.client.session[hotcold.SESSION_KEY]
        self.assertEqual((state["mode"], state["guesses"], state["over"]), ("free", [], ""))
        self.assertNotEqual(state["secret"], secret)

    def test_game_lives_outside_the_nose(self):
        self.assertEqual(reverse("hotcold:game"), "/chaud-froid/")
        page = self.client.get("/chaud-froid/")
        self.assertContains(page, 'href="/chaud-froid/"')  # entrée du menu, à côté du blind test
        self.assertNotContains(page, "Modes du Nez")
        self.assertRedirects(self.client.get("/le-nez/chaud-froid/"), "/chaud-froid/",
                             status_code=301, fetch_redirect_response=False)

    def test_winning_by_choice(self):
        self.client.get(reverse("hotcold:game"))
        secret = self.client.session[hotcold.SESSION_KEY]["secret"]
        r = self.client.post(reverse("hotcold:guess"), {"q": "x", "choice": f"profile:{secret}"},
                             HTTP_HX_REQUEST="true")
        self.assertContains(r, "Trouvé en 1 proposition")


class HotColdRankingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())

    def _win(self, wrong=0):
        """Joue le défi du jour : `wrong` mauvaises propositions, puis la bonne."""
        self.client.get(reverse("hotcold:game"))
        secret = self.client.session[hotcold.SESSION_KEY]["secret"]
        for q in ["syrah", "chardonnay", "cassis", "Bourgogne"][:wrong]:
            self.client.post(reverse("hotcold:guess"), {"q": q}, HTTP_HX_REQUEST="true")
        return self.client.post(reverse("hotcold:guess"), {"q": "x", "choice": f"profile:{secret}"},
                                HTTP_HX_REQUEST="true")

    def test_points(self):
        self.assertEqual(hotcold.points(1, True), 100)
        self.assertEqual(hotcold.points(5, True), 88)
        self.assertEqual(hotcold.points(200, True), hotcold.MIN_WIN_POINTS)
        self.assertEqual(hotcold.points(7, False), 0)

    def test_daily_win_by_logged_in_player_is_ranked(self):
        User.objects.create_user("lea", "l@example.com", "Un-Bon-Cru-2026")
        self.client.login(username="lea", password="Un-Bon-Cru-2026")
        r = self._win(wrong=2)
        res = HotColdResult.objects.get()
        self.assertEqual((res.outcome, res.guesses, res.score), ("won", 3, 94))
        self.assertContains(r, "Classé au défi du jour : 94 points")
        self.assertContains(r, "lea")  # dans le classement du jour de la page

    def test_replaying_does_not_change_first_result(self):
        User.objects.create_user("lea", "l@example.com", "Un-Bon-Cru-2026")
        self.client.login(username="lea", password="Un-Bon-Cru-2026")
        self._win(wrong=3)
        self.client.post(reverse("hotcold:new"), {"mode": "daily"})
        self._win(wrong=0)
        res = HotColdResult.objects.get()
        self.assertEqual((res.guesses, res.score), (4, 91))

    def test_abandon_is_ranked_with_zero(self):
        User.objects.create_user("lea", "l@example.com", "Un-Bon-Cru-2026")
        self.client.login(username="lea", password="Un-Bon-Cru-2026")
        self.client.get(reverse("hotcold:game"))
        self.client.post(reverse("hotcold:guess"), {"q": "syrah"}, HTTP_HX_REQUEST="true")
        self.client.post(reverse("hotcold:give_up"))
        res = HotColdResult.objects.get()
        self.assertEqual((res.outcome, res.score), ("abandoned", 0))

    def test_anonymous_and_free_games_are_not_ranked(self):
        self._win()
        self.assertEqual(HotColdResult.objects.count(), 0)
        page = self.client.get(reverse("hotcold:game"))
        self.assertContains(page, "Connectez-vous")
        User.objects.create_user("lea", "l@example.com", "Un-Bon-Cru-2026")
        self.client.login(username="lea", password="Un-Bon-Cru-2026")
        self.client.post(reverse("hotcold:new"), {"mode": "free"})
        secret = self.client.session[hotcold.SESSION_KEY]["secret"]
        self.client.post(reverse("hotcold:guess"), {"q": "x", "choice": f"profile:{secret}"},
                         HTTP_HX_REQUEST="true")
        self.assertEqual(HotColdResult.objects.count(), 0)

    def test_leaderboard_orders_by_points_then_guesses_and_shows_on_ranking_page(self):
        from django.utils import timezone
        today = timezone.localdate()
        a = User.objects.create_user("a", "a@example.com", "Un-Bon-Cru-2026")
        b = User.objects.create_user("b", "b@example.com", "Un-Bon-Cru-2026")
        HotColdResult.objects.create(user=a, day=today, secret="x", outcome="won", guesses=9, score=76)
        HotColdResult.objects.create(user=b, day=today, secret="x", outcome="won", guesses=2, score=97)
        self.assertEqual([g.user.username for g in hotcold.leaderboard(today)], ["b", "a"])
        page = self.client.get(reverse("accounts:ranking") + "?jeu=hotcold")
        self.assertContains(page, reverse("accounts:player", args=["b"]))
        self.assertEqual([r["username"] for r in page.context["today"]], ["b", "a"])


class LearnedFallbackTests(TestCase):
    """Le Nez : un arôme absent d'un profil profite des arômes voisins dans l'espace appris."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())

    def setUp(self):
        predictor.reset()

    def test_kernel_is_available_and_bounded(self):
        m = predictor.model()
        kernel = predictor.default_fallback(m)
        self.assertTrue(callable(kernel))
        a, b, c = (Aroma.objects.get(name=n).id for n in ("framboise", "groseille", "hydrocarbure"))
        self.assertGreater(kernel(a, b), kernel(a, c))
        self.assertEqual(kernel(a, b), kernel(b, a))
        self.assertTrue(0 <= kernel(a, c) <= kernel(a, b) <= 1)

    def test_close_aroma_never_beats_the_same_profile_with_the_exact_one(self):
        m = predictor.model()
        kernel = predictor.default_fallback(m)
        a = Aroma.objects.get(name="framboise").id
        for p in m.profiles[:40]:
            if a in p["weights"]:
                continue
            soft, detail = predictor._aroma_term(m, p, a, kernel)
            self.assertLess(soft, 1 + predictor.ALPHA + predictor.BETA)
            self.assertIn(detail["match"], {"family", "none"})

    def test_explanation_names_the_neighbour(self):
        ids = [Aroma.objects.get(name=n).id for n in ("litchi", "rose")]
        results = predictor.predict(ids, top=8)["results"]
        self.assertEqual(results[0]["profile"]["name"], "Alsace gewurztraminer")
        near = [m.get("near") for r in results for m in r["matches"] if m["match"] == "family"]
        self.assertTrue(near and all(near))

    def test_family_fallback_when_vectors_are_missing(self):
        m = predictor.model()
        m.kernel = None
        self.assertEqual(predictor.default_fallback(m), "family")
        ids = [Aroma.objects.get(name="framboise").id]
        self.assertTrue(predictor.predict(ids)["results"])
        predictor.reset()

    def test_unused_aroma_still_matches_through_its_family(self):
        unused = Aroma.objects.filter(profile_links__isnull=True).first()
        if unused is None:
            self.skipTest("tous les arômes sont utilisés")
        self.assertTrue(predictor.predict([unused.id])["results"])
