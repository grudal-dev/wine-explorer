from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import translation

from apps.catalog.models import WineProfile
from apps.molecules import facts, graph
from apps.molecules.models import ProfileMolecule


class OxidativeAgeingTests(TestCase):
    """Élevage oxydatif : thiols variétaux et acétate d'isoamyle ne sont plus reliés au vin."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", country="all", stdout=StringIO())

    def test_flagged_profiles(self):
        flagged = set(WineProfile.objects.filter(oxidative=True).values_list("slug", flat=True))
        self.assertTrue({"porto-tawny-10-ans", "porto-colheita"} <= flagged)
        # Le style oxydatif l'est d'office ; un Porto Ruby ne l'est pas.
        for p in WineProfile.objects.filter(style="oxydatif"):
            self.assertIn(p.slug, flagged)
        self.assertNotIn("porto-ruby", flagged)

    def test_fragile_molecules_absent_from_oxidative_wines(self):
        fragile = {"3-sulfanylhexanol", "4-mmp", "acetate-de-3-sulfanylhexyle", "acetate-disoamyle"}
        links = ProfileMolecule.objects.filter(profile__oxidative=True, molecule__slug__in=fragile)
        self.assertFalse(links.exists(), list(links.values_list("profile__slug", "molecule__slug")))
        # Ailleurs, rien ne change : le Sancerre garde ses thiols.
        self.assertTrue(ProfileMolecule.objects.filter(
            profile__slug="sancerre-blanc", molecule__slug="3-sulfanylhexanol").exists())


    def test_sotolon_follows_oxidative_ageing_not_fortification(self):
        # Un ruby, un LBV, un vintage ou un muscat muté n'ont pas de sotolon ; le tawny, oui, en force 3.
        for slug in ["porto-ruby", "porto-late-bottled-vintage", "porto-vintage", "muscat-de-rivesaltes-blanc"]:
            self.assertFalse(ProfileMolecule.objects.filter(profile__slug=slug, molecule__slug="sotolon").exists(), slug)
        self.assertFalse(ProfileMolecule.objects.filter(profile__slug="porto-ruby", molecule__slug="mnd").exists())
        self.assertFalse(ProfileMolecule.objects.filter(profile__slug="muscat-de-rivesaltes-blanc", molecule__slug="mnd").exists())
        tawny = ProfileMolecule.objects.get(profile__slug="porto-tawny-10-ans", molecule__slug="sotolon")
        self.assertEqual(tawny.strength, 3)
        self.assertIn("silvaferreira2003", {r["ref"] for r in tawny.reasons})


class BouquetNotesTests(TestCase):
    """Vue d'un vin : la bulle porte l'arôme du vin qui justifie le lien ; les éléments naturels
    sans arôme commun avec le vin sont marqués « lointains » et limités."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", country="all", stdout=StringIO())

    def setUp(self):
        graph.reset()

    def tearDown(self):
        translation.activate("fr")

    def _nodes(self, slug):
        data = graph.build("profile", slug)
        return {e["data"]["id"]: e["data"] for e in data["elements"] if e["group"] == "nodes"}, data

    def test_note_is_the_wine_aroma(self):
        nodes, _ = self._nodes("porto-tawny-10-ans")
        furaneol = nodes["molecule:furaneol"]
        self.assertEqual(furaneol["note"], "caramel")       # pas « fraise »
        self.assertEqual(furaneol["odor"], "fraise")        # l'odeur propre reste dans la donnée
        self.assertNotEqual(furaneol["hue"], graph.data().molecules["furaneol"]["hue"])
        # Reliée par un arôme du vin : bulle pleine ; par la seule couleur (diacétyle d'un rouge) : grisée.
        self.assertTrue(furaneol.get("direct"))
        self.assertFalse(nodes["molecule:diacetyle"].get("direct"))

    def test_near_and_far_sources(self):
        nodes, data = self._nodes("porto-tawny-10-ans")
        self.assertTrue(nodes["source:cannelle"].get("near"))
        self.assertFalse(nodes["source:fraise"].get("near"))
        far_per_molecule = {}
        for e in data["elements"]:
            d = e["data"]
            if e["group"] == "edges" and d["kind"] == "found_in" and not d.get("near"):
                far_per_molecule[d["source"]] = far_per_molecule.get(d["source"], 0) + 1
        self.assertTrue(far_per_molecule)
        self.assertLessEqual(max(far_per_molecule.values()), graph.MAX_FAR_PER_MOLECULE)

    def test_note_translated(self):
        translation.activate("en")
        nodes, _ = self._nodes("porto-tawny-10-ans")
        self.assertEqual(nodes["molecule:sotolon"]["note"], "walnut")


class FactTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", country="all", stdout=StringIO())

    def tearDown(self):
        translation.activate("fr")

    def test_every_fact_points_to_a_molecule_and_a_reference(self):
        for f in facts._facts():
            translation.activate("fr")
            shown = facts._render(f)
            self.assertIsNotNone(shown["molecule"], f["molecule"])
            self.assertIsNotNone(shown["reference"], f["ref"])
            self.assertTrue(f["text"] and f["text_en"])

    def test_molecule_page_shows_its_fact(self):
        html = self.client.get("/molecules/rotundone/").content.decode()
        self.assertIn("Le saviez-vous ?", html)
        self.assertIn("une personne sur cinq", html)
        html = self.client.get("/en/molecules/rotundone/").content.decode()
        self.assertIn("Did you know?", html)
        self.assertIn("one person in five", html)

    def test_profile_fact_is_about_one_of_its_molecules_and_stable(self):
        tawny = WineProfile.objects.get(slug="porto-tawny-10-ans")
        first = facts.for_profile(tawny, seed="abc")
        self.assertEqual(first, facts.for_profile(tawny, seed="abc"))
        own = set(ProfileMolecule.objects.filter(profile=tawny).values_list("molecule__slug", flat=True))
        self.assertIn(first["molecule"].slug, own)

    def test_facts_never_name_an_appellation(self):
        # L'encart sort aussi en fin de blind test : il ne doit pas citer d'appellation.
        from apps.catalog.models import Appellation
        from apps.catalog.text import normalize

        names = {normalize(a.name) for a in Appellation.objects.all() if len(a.name) > 4}
        for f in facts._facts():
            text = normalize(f["text"])
            self.assertFalse([n for n in names if f" {n} " in f" {text} "], f["molecule"])
