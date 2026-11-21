from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.molecules import graph
from apps.molecules.models import Molecule


class AttackTests(TestCase):
    """L'« attaque » (data/attack.yaml) règle la hauteur des bulles du bouquet ; elle n'est jamais affichée."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", country="all", stdout=StringIO())

    def test_every_molecule_has_a_level(self):
        self.assertFalse(Molecule.objects.exclude(attack__in=(1, 2, 3)).exists())
        self.assertGreater(Molecule.objects.filter(attack=1).count(), 5)
        self.assertGreater(Molecule.objects.filter(attack=3).count(), 5)

    def test_pepper_is_smelled_at_once(self):
        """Peu volatile mais perçue à 16 ng/L : la rotundone est en haut, malgré sa masse."""
        self.assertEqual(Molecule.objects.get(slug="rotundone").attack, 1)
        self.assertEqual(Molecule.objects.get(slug="vanilline").attack, 3)

    def test_graph_carries_the_level_but_no_label(self):
        data = graph.build("profile", "cote-rotie-rouge")
        mols = [e["data"] for e in data["elements"] if e["group"] == "nodes" and e["data"]["type"] == "molecule"]
        self.assertTrue(mols)
        self.assertTrue(all(m["att"] in (1, 2, 3) for m in mols))
