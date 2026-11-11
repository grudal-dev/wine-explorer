from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.embeddings.nodes import cousins, describe
from apps.embeddings.space import DATA_FILE, space
from apps.explorer.graph import full_graph


class SpaceTests(TestCase):
    """Le fichier de vecteurs livré avec le projet correspond aux données chargées."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())

    def test_file_is_shipped_and_covers_the_graph(self):
        self.assertTrue(DATA_FILE.exists(), "lancer `python manage.py train_embeddings`")
        sp = space()
        missing = [n for n in full_graph().nodes if n not in sp]
        self.assertEqual(missing, [], "données modifiées depuis l'entraînement : relancer train_embeddings")
        self.assertGreaterEqual(sp.meta["auc_held_out"], 0.8)

    def test_vectors_are_unit_length(self):
        sp = space()
        for node_id in sp.ids[:50]:
            self.assertAlmostEqual(sp.similarity(node_id, node_id), 1.0, places=2)

    def test_neighbours_make_sense(self):
        sp = space()
        near = [n for n, _s in sp.neighbours("profile:cote-rotie-rouge", types=("profile",), k=6)]
        northern_rhone = {"profile:hermitage-rouge", "profile:saint-joseph-rouge", "profile:cornas-rouge",
                          "profile:crozes-hermitage-rouge"}
        self.assertGreaterEqual(len(northern_rhone & set(near)), 3)
        near = [n for n, _s in sp.neighbours("profile:sauternes-blanc", types=("profile",), k=3)]
        self.assertIn("profile:monbazillac-blanc", near)
        # Un rouge tannique est plus loin d'un Chablis qu'un autre blanc vif.
        self.assertGreater(sp.similarity("profile:chablis-blanc", "profile:muscadet-sevre-et-maine-blanc"),
                           sp.similarity("profile:chablis-blanc", "profile:madiran-rouge"))

    def test_ranks(self):
        sp = space()
        ranks = sp.ranks("profile:chablis-blanc")
        self.assertEqual(len(ranks), len(sp.ids) - 1)
        self.assertEqual(sorted(ranks.values())[:3], [1, 2, 3])
        self.assertNotIn("profile:chablis-blanc", ranks)

    def test_unknown_nodes(self):
        sp = space()
        self.assertIsNone(sp.similarity("profile:chablis-blanc", "grape:inconnu"))
        self.assertEqual(sp.neighbours("grape:inconnu"), [])
        self.assertEqual(cousins("grape:inconnu"), [])
        self.assertIsNone(describe("grape:inconnu"))

    def test_cousins(self):
        groups = cousins("grape:syrah")
        self.assertEqual([g["kind"] for g in groups][:2], ["grape", "profile"])
        grapes = groups[0]["items"]
        self.assertTrue(all(0 < it["percent"] <= 100 for it in grapes))
        self.assertFalse(any(it["id"] == "grape:syrah" for it in grapes))
        # Les vins de Syrah sont des liens déjà écrits ; les cépages voisins, des parentés déduites.
        self.assertTrue(any(it["linked"] for it in groups[1]["items"]))
        self.assertFalse(any(it["linked"] for it in grapes))


class ViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())

    def test_map_page_and_api(self):
        page = self.client.get(reverse("embeddings:map"))
        self.assertContains(page, "Carte des goûts")
        nodes = self.client.get(reverse("embeddings:api_map")).json()["nodes"]
        wines = [n for n in nodes if n["type"] == "profile"]
        self.assertEqual(len(wines), 98)
        self.assertTrue(all(-1.01 <= n["x"] <= 1.01 and -1.01 <= n["y"] <= 1.01 for n in nodes))
        self.assertIn(wines[0]["wine"], {"rouge", "blanc", "rose"})

    def test_neighbours_api_and_panel(self):
        data = self.client.get(reverse("embeddings:api_neighbours"), {"id": "profile:chablis-blanc"}).json()
        self.assertEqual(len(data["neighbours"]), 6)
        self.assertTrue(all(n["id"].startswith("profile:") for n in data["neighbours"]))
        self.assertEqual(self.client.get(reverse("embeddings:api_neighbours"), {"id": "x:y"}).json()["neighbours"], [])
        panel = self.client.get(reverse("embeddings:panel", args=["profile:chablis-blanc"]))
        self.assertContains(panel, "Ce qui lui ressemble")
        self.assertEqual(self.client.get(reverse("embeddings:panel", args=["profile:nope"])).status_code, 404)

    def test_cousins_on_detail_pages(self):
        for url in ("/catalogue/vins/chablis-blanc/", "/catalogue/cepages/syrah/", "/catalogue/aromes/violette/",
                    "/catalogue/appellations/chablis/", "/molecules/rotundone/"):
            self.assertContains(self.client.get(url), "Ce qui lui ressemble", msg_prefix=url)

    def test_english(self):
        page = self.client.get(reverse("embeddings:map"), HTTP_ACCEPT_LANGUAGE="en")
        self.assertContains(page, "Taste map")
        panel = self.client.get(reverse("embeddings:panel", args=["aroma:violette"]), HTTP_ACCEPT_LANGUAGE="en")
        self.assertContains(panel, "raspberry")
        from django.utils import translation
        translation.activate("fr")
