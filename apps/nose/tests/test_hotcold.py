from datetime import date
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import Aroma
from apps.embeddings.space import space
from apps.nose import hotcold, predictor


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
        page = self.client.get(reverse("nose:hot_cold"))
        self.assertContains(page, "Chaud-froid")
        secret = self.client.session[hotcold.SESSION_KEY]["secret"]
        self.assertNotContains(page, secret)
        r = self.client.post(reverse("nose:hot_cold_guess"), {"q": "syrah"}, HTTP_HX_REQUEST="true")
        self.assertContains(r, 'id="hotcold"')
        self.assertContains(r, "Syrah")
        self.assertNotContains(r, secret)
        r = self.client.post(reverse("nose:hot_cold_guess"), {"q": "zzzz"}, HTTP_HX_REQUEST="true")
        self.assertContains(r, "pas dans le graphe")
        self.assertEqual(self.client.session[hotcold.SESSION_KEY]["guesses"], ["grape:syrah"])
        self.client.post(reverse("nose:hot_cold_give_up"))
        page = self.client.get(reverse("nose:hot_cold"))
        self.assertContains(page, "Partie abandonnée")
        self.assertContains(page, f"/catalogue/vins/{secret}/")
        self.client.post(reverse("nose:hot_cold_new"), {"mode": "free"})
        state = self.client.session[hotcold.SESSION_KEY]
        self.assertEqual((state["mode"], state["guesses"], state["over"]), ("free", [], ""))
        self.assertNotEqual(state["secret"], secret)

    def test_winning_by_choice(self):
        self.client.get(reverse("nose:hot_cold"))
        secret = self.client.session[hotcold.SESSION_KEY]["secret"]
        r = self.client.post(reverse("nose:hot_cold_guess"), {"q": "x", "choice": f"profile:{secret}"},
                             HTTP_HX_REQUEST="true")
        self.assertContains(r, "Trouvé en 1 proposition")


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
