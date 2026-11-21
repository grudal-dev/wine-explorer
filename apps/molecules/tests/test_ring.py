from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.molecules.models import ProfileMolecule


class MoleculeRingTests(TestCase):
    """Vue d'une molécule : plus de vins en couronne, et tous listés dans la fiche."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", country="all", stdout=StringIO())

    def test_api_takes_more_wines_on_request(self):
        base = self.client.get("/molecules/api/graphe/?kind=molecule&slug=rotundone").json()["stats"]
        more = self.client.get("/molecules/api/graphe/?kind=molecule&slug=rotundone&vins=32").json()["stats"]
        total = ProfileMolecule.objects.filter(molecule__slug="rotundone").count()
        self.assertEqual(base["profiles"], min(18, total))
        self.assertEqual(more["profiles"], min(32, total))
        self.assertEqual(more["profiles"] + more["truncated"], total)
        bad = self.client.get("/molecules/api/graphe/?kind=molecule&slug=rotundone&vins=abc").json()["stats"]
        self.assertEqual(bad["profiles"], base["profiles"])

    def test_panel_lists_every_wine(self):
        total = ProfileMolecule.objects.filter(molecule__slug="rotundone").count()
        html = self.client.get("/molecules/fiche/molecule:rotundone/").content.decode()
        self.assertIn(f"Dans {total} vins", html)
        self.assertEqual(html.count('class="tag tag--profile"'), total)
