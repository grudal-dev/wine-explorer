import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from apps.catalog.index import search_aroma, search_guess
from apps.catalog.models import Appellation, Grape, WineProfile
from apps.catalog.text import normalize


class SeedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())

    def test_seed_loaded_and_consistent(self):
        self.assertGreater(WineProfile.objects.count(), 80)
        for p in WineProfile.objects.prefetch_related("profile_grapes"):
            self.assertEqual(sum(pg.share for pg in p.profile_grapes.all()), 100, p.name)
            self.assertGreaterEqual(p.profile_aromas.count(), 4, p.name)

    def test_idempotent(self):
        before = (WineProfile.objects.count(), Grape.objects.count())
        call_command("load_seed", stdout=StringIO())
        self.assertEqual(before, (WineProfile.objects.count(), Grape.objects.count()))

    def test_check_mode_does_not_write(self):
        WineProfile.objects.all().delete()
        call_command("load_seed", "--check", stdout=StringIO())
        self.assertEqual(WineProfile.objects.count(), 0)


class TextTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())

    def test_normalize(self):
        self.assertEqual(normalize("Côte-Rôtie"), "cote rotie")
        self.assertEqual(normalize("  Cœur  d'Alène "), "coeur d alene")

    def test_guess_resolves_synonyms_and_accents(self):
        self.assertEqual(search_guess("cote rotie")[0].label, "Côte-Rôtie")
        self.assertEqual(search_guess("Shiraz")[0].label, "Syrah")
        self.assertEqual(search_guess("côt")[0].label, "Malbec")

    def test_aroma_synonyms(self):
        self.assertEqual(search_aroma("pierre à fusil")[0].label, "silex")
        self.assertEqual(search_aroma("pétrole")[0].label, "hydrocarbure")


class InaoImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())

    def test_import_enriches_and_creates(self):
        csv_text = (
            "Département;Commune;CI;Aire géographique;IDA;Produit;Signe\n"
            "89;Chablis;89068;Chablis;1234;Chablis blanc;AOC\n"
            "89;Fleys;89164;Chablis;1234;Chablis blanc;AOC\n"
            "34;Aniane;34010;Saint-Guilhem-le-Désert;9999;Saint-Guilhem-le-Désert rouge;IGP\n"
            "75;Paris;75056;Brie de Meaux;5555;Brie de Meaux;AOC\n"
        )
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "inao.csv"
            path.write_text(csv_text, encoding="utf-8")
            call_command("import_inao", str(path), "--create", stdout=StringIO())
        chablis = Appellation.objects.get(slug="chablis")
        self.assertEqual(chablis.inao_code, "1234")
        self.assertEqual(chablis.communes_count, 2)
        created = Appellation.objects.get(slug="saint-guilhem-le-desert")
        self.assertEqual(created.classification, "IGP")
        self.assertFalse(Appellation.objects.filter(slug="brie-de-meaux").exists())
