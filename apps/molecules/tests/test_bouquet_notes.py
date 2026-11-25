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
    """Vue d'un vin : la bulle porte le nom de la molécule, prend la couleur de l'arôme du vin qu'elle
    explique, et ce même arôme est au bout de son trait."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", country="all", stdout=StringIO())

    def setUp(self):
        graph.reset()

    def tearDown(self):
        translation.activate("fr")

    def _nodes(self, slug, common=None):
        data = graph.build("profile", slug, common=common)
        return {e["data"]["id"]: e["data"] for e in data["elements"] if e["group"] == "nodes"}, data

    def test_note_is_the_wine_aroma(self):
        nodes, _ = self._nodes("porto-tawny-10-ans")
        furaneol = nodes["molecule:furaneol"]
        self.assertEqual(furaneol["note"], "caramel")       # pas « fraise »
        self.assertEqual(furaneol["odor"], "fraise")        # l'odeur propre reste dans la donnée
        self.assertNotEqual(furaneol["hue"], graph.data().molecules["furaneol"]["hue"])
        # Reliée par un arôme du vin : bulle pleine ; par la seule couleur (diacétyle d'un rouge) : grisée.
        self.assertTrue(furaneol.get("direct"))
        nodes, _ = self._nodes("porto-tawny-10-ans", common=True)
        self.assertFalse(nodes["molecule:diacetyle"].get("direct"))

    def test_aromas_replace_natural_elements(self):
        # Vue d'un vin : au bout des traits, les arômes du vin que chaque molécule explique ; plus
        # d'éléments naturels (souchet rond, jacquier, truffe noire…), qui renvoyaient loin du vin.
        nodes, data = self._nodes("porto-tawny-10-ans", common=True)
        self.assertFalse([n for n in nodes.values() if n["type"] == "source"])
        self.assertEqual(nodes["aroma:caramel"]["layer"], 2)
        wine_aromas = set(WineProfile.objects.get(slug="porto-tawny-10-ans").aromas.values_list("slug", flat=True))
        for e in data["elements"]:
            d = e["data"]
            if e["group"] == "edges" and d["kind"] == "evokes":
                self.assertIn(d["target"].split(":", 1)[1], wine_aromas)
        self.assertIn({"source": "molecule:furaneol", "target": "aroma:caramel"},
                      [{"source": e["data"]["source"], "target": e["data"]["target"]} for e in data["elements"]
                       if e["group"] == "edges" and e["data"]["kind"] == "evokes"])
        stats = data["stats"]
        self.assertGreater(stats["aromas"], 0)
        self.assertLessEqual(stats["aromas"], stats["aromas_total"])

    def test_one_label_per_aroma(self):
        # Deux molécules qui donnent « rose » pointent vers la même étiquette.
        nodes, data = self._nodes("alsace-gewurztraminer")
        rose = [e for e in data["elements"] if e["group"] == "edges" and e["data"]["target"] == "aroma:rose"]
        self.assertGreaterEqual(len(rose), 2)

    def test_grape_markers_need_their_grape(self):
        # La « rose » d'un Barolo ne vient ni de l'oxyde de rose ni du géraniol (marqueurs du Gewurztraminer
        # et des Muscats) ; dans le Gewurztraminer, le descripteur s'ajoute au cépage.
        for mol in ("oxyde-de-rose-cis", "geraniol", "citronellol", "nerol"):
            self.assertFalse(ProfileMolecule.objects.filter(profile__slug="barolo-rouge", molecule__slug=mol).exists())
        gw = ProfileMolecule.objects.get(profile__slug="alsace-gewurztraminer", molecule__slug="oxyde-de-rose-cis")
        self.assertEqual({r["basis"] for r in gw.reasons} >= {"grape", "aroma"}, True)

    def test_aroma_panel(self):
        from django.urls import reverse

        url = reverse("molecules:panel", args=["aroma:poivre-noir"]) + "?vin=cote-rotie-rouge"
        r = self.client.get(url)
        self.assertContains(r, "rotundone")
        self.assertContains(r, 'data-start="source:poivre-noir"')

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
