import json
from io import StringIO
from pathlib import Path

import yaml
from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import WineProfile
from apps.molecules import graph
from apps.molecules.models import Basis, Molecule, NaturalSource, Occurrence, ProfileMolecule, Reference, slug_for

DATA = Path(__file__).resolve().parents[1] / "data"


class DataIntegrityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())  # enchaîne load_molecules

    def test_everything_loaded(self):
        self.assertEqual(Molecule.objects.count(), len(yaml.safe_load((DATA / "molecules.yaml").read_text())))
        self.assertGreater(NaturalSource.objects.count(), 30)
        self.assertGreater(ProfileMolecule.objects.count(), 300)

    def test_every_molecule_is_drawn_and_computed(self):
        computed = json.loads((DATA / "computed.json").read_text())
        for m in Molecule.objects.all():
            with self.subTest(molecule=m.name):
                self.assertIn(m.slug, computed, "lancer render_molecules")
                self.assertTrue(m.formula)
                self.assertTrue((Path(settings.BASE_DIR) / "static" / m.structure_static).exists())

    def test_every_link_is_sourced(self):
        keys = set(Reference.objects.values_list("key", flat=True))
        for pm in ProfileMolecule.objects.all():
            self.assertTrue(pm.reasons)
            for r in pm.reasons:
                self.assertIn(r["ref"], keys)
        self.assertFalse(Occurrence.objects.filter(reference__isnull=True).exists())

    def test_no_orphan_reference(self):
        used = {r["ref"] for pm in ProfileMolecule.objects.all() for r in pm.reasons}
        used |= set(Occurrence.objects.values_list("reference__key", flat=True))
        used |= set(Molecule.references.through.objects.values_list("reference__key", flat=True))
        self.assertEqual(set(Reference.objects.values_list("key", flat=True)) - used, set())

    def test_check_mode_does_not_write(self):
        Molecule.objects.all().delete()
        call_command("load_molecules", "--check", stdout=StringIO())
        self.assertEqual(Molecule.objects.count(), 0)

    def test_slug_for_greek(self):
        self.assertEqual(slug_for("β-damascénone"), "beta-damascenone")
        self.assertEqual(slug_for("1,8-cinéole"), "1-8-cineole")


class RuleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())

    def link(self, profile, molecule):
        return ProfileMolecule.objects.get(profile__slug=profile, molecule__slug=molecule)

    def test_varietal_markers(self):
        rot = self.link("cote-rotie-rouge", "rotundone")
        self.assertEqual((rot.strength, rot.basis), (3, Basis.GRAPE))
        self.assertIn("Syrah (95 %", rot.reasons[0]["label"])
        self.assertEqual(self.link("sancerre-blanc", "4-mmp").strength, 3)
        self.assertEqual(self.link("alsace-gewurztraminer", "oxyde-de-rose-cis").strength, 3)
        self.assertEqual(self.link("alsace-riesling", "tdn").strength, 3)

    def test_style_rule(self):
        link = self.link("chateau-chalon-blanc", "sotolon")
        self.assertEqual((link.strength, link.basis), (3, Basis.STYLE))

    def test_min_share(self):
        # 5 % de Viognier dans la Côte-Rôtie : pas assez pour les règles de cépage (seuil 15 %).
        self.assertFalse(ProfileMolecule.objects.filter(
            profile__slug="sancerre-blanc", molecule__slug="rotundone").exists())

    def test_aroma_rule_is_capped(self):
        for pm in ProfileMolecule.objects.filter(basis=Basis.AROMA):
            self.assertLessEqual(pm.strength, 2)

    def test_universal_reaches_everyone(self):
        n = WineProfile.objects.count()
        self.assertEqual(ProfileMolecule.objects.filter(molecule__slug="acetate-disoamyle").count(), n)
        beaujolais = self.link("beaujolais-rouge", "acetate-disoamyle")
        self.assertEqual(beaujolais.basis, Basis.AROMA)  # la « banane » prime sur le socle commun


class GraphAndViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())

    def setUp(self):
        graph.reset()

    def test_profile_graph_layers(self):
        g = graph.build("profile", "cote-rotie-rouge")
        nodes = {e["data"]["id"]: e["data"] for e in g["elements"] if e["group"] == "nodes"}
        self.assertEqual(nodes["profile:cote-rotie-rouge"]["layer"], 0)
        self.assertEqual(nodes["molecule:rotundone"]["layer"], 1)
        self.assertEqual(nodes["source:poivre-noir"]["layer"], 2)
        self.assertNotIn("molecule:acetate-disoamyle", nodes)  # socle commun masqué
        self.assertGreater(g["stats"]["hidden_common"], 0)
        with_common = graph.build("profile", "cote-rotie-rouge", common=True)
        self.assertIn("molecule:acetate-disoamyle", {e["data"]["id"] for e in with_common["elements"]})

    def test_graph_lists_its_sources(self):
        refs = {r["key"]: r for r in graph.build("profile", "cote-rotie-rouge")["references"]}
        self.assertIn("wood2008", refs)  # Syrah → rotundone, et rotundone → poivre noir
        self.assertGreaterEqual(refs["wood2008"]["links"], 2)
        self.assertTrue(refs["wood2008"]["link"].startswith("https://doi.org/"))

    def test_source_graph_is_capped(self):
        g = graph.build("source", "chene")
        self.assertLessEqual(g["stats"]["profiles"], graph.MAX_PROFILES)
        ids = {e["data"]["id"] for e in g["elements"] if e["group"] == "nodes"}
        for e in g["elements"]:
            if e["group"] == "edges":
                self.assertIn(e["data"]["source"], ids)
                self.assertIn(e["data"]["target"], ids)

    def test_unknown_entity(self):
        self.assertIsNone(graph.build("profile", "inexistant"))
        self.assertIsNone(graph.build("autre", "x"))

    def test_search(self):
        kinds = {r["kind"] for r in graph.search("poivr")}
        self.assertIn("source", kinds)

    def test_pages_and_api(self):
        urls = [
            reverse("molecules:explorer"), reverse("molecules:list"), reverse("molecules:bibliography"),
            reverse("molecules:molecule", args=["rotundone"]),
            reverse("molecules:source", args=["poivre-noir"]),
            reverse("molecules:api_graph") + "?kind=source&slug=rose-de-damas",
            reverse("molecules:api_search") + "?q=sot",
            reverse("molecules:panel", args=["molecule:rotundone"]) + "?vin=cote-rotie-rouge",
            reverse("molecules:panel", args=["source:chene"]),
            reverse("molecules:panel", args=["profile:sancerre-blanc"]),
            reverse("catalog:profile", args=["sancerre-blanc"]),
            reverse("catalog:aroma", args=["vanille"]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_panel_explains_the_link(self):
        r = self.client.get(reverse("molecules:panel", args=["molecule:rotundone"]) + "?vin=cote-rotie-rouge")
        self.assertContains(r, "Syrah")
        self.assertContains(r, "Wood et al. 2008")

    def test_404s(self):
        self.assertEqual(self.client.get(reverse("molecules:api_graph") + "?kind=profile&slug=x").status_code, 404)
        self.assertEqual(self.client.get(reverse("molecules:panel", args=["autre:x"])).status_code, 404)
        self.assertEqual(self.client.get(reverse("molecules:molecule", args=["inexistante"])).status_code, 404)
