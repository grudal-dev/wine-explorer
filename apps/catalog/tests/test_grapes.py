from io import StringIO

import yaml
from django.core.management import call_command
from django.test import TestCase
from django.utils import translation

from apps.catalog.grapes import MERGED, apply_known_merges
from apps.catalog.index import search_guess
from apps.catalog.management.commands.load_seed import DATA_DIR
from apps.catalog.models import Grape, ProfileGrape, WineProfile
from apps.catalog.text import normalize


class GrapeReferenceTests(TestCase):
    """Un nom (nom ou synonyme) ne désigne qu'un cépage, tous pays confondus."""

    def test_one_name_one_grape(self):
        owner: dict[str, str] = {}
        for path in sorted(DATA_DIR.glob("*/grapes.yaml")):
            for item in yaml.safe_load(path.read_text(encoding="utf-8")):
                for label in [item["name"], *item.get("synonyms", [])]:
                    key = normalize(label)
                    self.assertIn(owner.setdefault(key, item["name"]), (item["name"],),
                                  f"« {label} » ({path.parent.name}) désigne déjà {owner[key]}")

    def test_merged_slugs_are_not_declared(self):
        declared = {normalize(item["name"]) for path in DATA_DIR.glob("*/grapes.yaml")
                    for item in yaml.safe_load(path.read_text(encoding="utf-8"))}
        for old in MERGED:
            self.assertNotIn(old.replace("-", " "), declared)


class GrapeMergeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", country="all", stdout=StringIO())

    def tearDown(self):
        translation.activate("fr")

    def test_local_names_resolve_to_one_grape(self):
        self.assertFalse(Grape.objects.filter(slug__in=MERGED).exists())
        patrimonio = WineProfile.objects.get(slug="patrimonio-rouge")
        self.assertIn("sangiovese", [pg.grape.slug for pg in patrimonio.profile_grapes.all()])
        vermentino = Grape.objects.get(slug="vermentino")
        self.assertEqual({"patrimonio-blanc", "vermentino-di-gallura-blanc"} - {
            pg.profile.slug for pg in vermentino.profile_links.select_related("profile")}, set())
        for label, expected in [("Rolle", "Vermentino"), ("Vermentinu", "Vermentino"),
                                ("Nielluccio", "Sangiovese"), ("Zibibbo", "Muscat d'Alexandrie")]:
            self.assertEqual(search_guess(label)[0].label, expected, label)

    def test_old_pages_redirect(self):
        for old, new in [("rolle", "vermentino"), ("nielluccio", "sangiovese"), ("niellucciu", "sangiovese")]:
            r = self.client.get(f"/catalogue/cepages/{old}/")
            self.assertEqual(r.status_code, 301, old)
            self.assertTrue(r["Location"].endswith(f"/cepages/{new}/"), r["Location"])
        r = self.client.get("/en/catalogue/cepages/rolle/")
        self.assertEqual(r.status_code, 301)
        self.assertTrue(r["Location"].startswith("/en/"), r["Location"])
        self.assertEqual(self.client.get("/catalogue/cepages/inconnu/").status_code, 404)

    def test_reload_merges_a_stale_grape(self):
        """Base remplie avant la fusion : load_seed rattache les vins et supprime l'ancienne fiche."""
        vermentino = Grape.objects.get(slug="vermentino")
        rolle = Grape.objects.create(name="Rolle", slug="rolle", skin="blanc")
        ProfileGrape.objects.filter(grape=vermentino).update(grape=rolle)
        call_command("load_seed", country="all", skip_molecules=True, stdout=StringIO())
        self.assertFalse(Grape.objects.filter(slug="rolle").exists())
        self.assertTrue(ProfileGrape.objects.filter(grape__slug="vermentino", profile__slug="patrimonio-blanc").exists())

    def test_migration_merge_adds_shares(self):
        """Un vin qui portait les deux fiches garde une seule ligne, parts additionnées."""
        sangiovese = Grape.objects.get(slug="sangiovese")
        old = Grape.objects.create(name="Nielluccio", slug="nielluccio", skin="noir", synonyms=["Niellucciu"])
        chianti = WineProfile.objects.get(slug="chianti-classico-rouge")
        link = chianti.profile_grapes.get(grape=sangiovese)
        link.share -= 10
        link.save()
        ProfileGrape.objects.create(profile=chianti, grape=old, share=10)
        self.assertEqual(apply_known_merges(Grape, ProfileGrape), 1)
        self.assertFalse(Grape.objects.filter(slug="nielluccio").exists())
        self.assertEqual(chianti.profile_grapes.get(grape=sangiovese).share, link.share + 10)
        self.assertEqual(sum(pg.share for pg in chianti.profile_grapes.all()), 100)
