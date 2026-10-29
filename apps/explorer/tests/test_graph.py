from io import StringIO

from django.core.management import call_command
from django.http import QueryDict
from django.test import TestCase
from django.urls import reverse

from apps.explorer.graph import GraphQuery, build_view, shortest_path


def q(qs: str) -> GraphQuery:
    return GraphQuery.from_params(QueryDict(qs))


class GraphTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())

    def node_ids(self, view):
        return {e["data"]["id"] for e in view["elements"] if e["group"] == "nodes"}

    def test_default_view_types(self):
        view = build_view(q(""))
        types = {e["data"]["type"] for e in view["elements"] if e["group"] == "nodes"}
        self.assertEqual(types, {"region", "appellation", "grape"})
        ids = self.node_ids(view)
        edges = [e["data"] for e in view["elements"] if e["group"] == "edges"]
        self.assertTrue(all(e["source"] in ids and e["target"] in ids for e in edges))

    def test_profiles_hidden_links_appellation_to_grape(self):
        view = build_view(q("types=appellation&types=grape"))
        edges = {(e["data"]["source"], e["data"]["target"]) for e in view["elements"] if e["group"] == "edges"}
        self.assertIn(("appellation:chablis", "grape:chardonnay"), edges)

    def test_color_filter(self):
        view = build_view(q("types=profile&colors=rose"))
        wines = {e["data"].get("wine") for e in view["elements"] if e["group"] == "nodes"}
        self.assertEqual(wines, {"rose"})

    def test_family_aggregation_without_aromas(self):
        view = build_view(q("types=appellation&types=family"))
        types = {e["data"]["type"] for e in view["elements"] if e["group"] == "nodes"}
        self.assertEqual(types, {"appellation", "family"})
        self.assertGreater(view["stats"]["edges"], 50)

    def test_focus_limits_neighbourhood(self):
        full = build_view(q("types=region&types=appellation"))
        focused = build_view(q("types=region&types=appellation&focus=region:alsace&depth=1"))
        self.assertLess(focused["stats"]["nodes"], full["stats"]["nodes"])
        self.assertIn("appellation:alsace", self.node_ids(focused))

    def test_shortest_path(self):
        path = shortest_path("appellation:chablis", "aroma:litchi")
        self.assertIsNotNone(path)
        self.assertEqual(path[0]["node"]["id"], "appellation:chablis")
        self.assertEqual(path[-1]["node"]["id"], "aroma:litchi")
        self.assertIsNone(shortest_path("appellation:chablis", "aroma:inconnu"))

    def test_api(self):
        r = self.client.get(reverse("explorer:api_graph"), {"types": ["region", "appellation"]})
        self.assertEqual(r.status_code, 200)
        self.assertIn("elements", r.json())
        r = self.client.get(reverse("explorer:api_search"), {"q": "pauil"})
        self.assertEqual(r.json()["results"][0]["id"], "appellation:pauillac")
        r = self.client.get(reverse("explorer:api_path"), {"a": "grape:syrah", "b": "region:alsace"})
        self.assertTrue(r.json()["path"])
        self.assertEqual(self.client.get(reverse("explorer:node", args=["grape:syrah"])).status_code, 200)
        self.assertEqual(self.client.get(reverse("explorer:node", args=["grape:nope"])).status_code, 404)
        self.assertEqual(self.client.get(reverse("explorer:explorer")).status_code, 200)
