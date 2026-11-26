from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from apps.catalog.models import Grape


class PrintSheetTests(TestCase):
    """Fiche aromatique imprimable d'un vin, et le Muscat : linalol en tête, nez de raisin frais."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", country="all", stdout=StringIO())

    def tearDown(self):
        translation.activate("fr")

    def test_sheet_lists_molecules_reasons_and_sources(self):
        r = self.client.get(reverse("molecules:print_sheet", args=["alsace-muscat"]))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("Alsace muscat", html)
        self.assertIn("data-bouquet", html)
        # Le linalol vient en premier : il explique l'arôme dominant (raisin frais), en force 3.
        rows = r.context["rows"]
        self.assertEqual(rows[0]["name"], "linalol")
        self.assertEqual(rows[0]["explains"][0]["label"], "raisin frais")
        self.assertTrue(all(row["stage"] for row in rows))
        self.assertTrue(r.context["references"])
        self.assertIn("Dans cet Alsace muscat", r.context["headline"])

    def test_sheet_unknown_wine(self):
        r = self.client.get(reverse("molecules:print_sheet", args=["nexiste-pas"]))
        self.assertEqual(r.status_code, 404)

    def test_sheet_in_english(self):
        r = self.client.get(reverse("molecules:print_sheet", args=["alsace-muscat"]), HTTP_ACCEPT_LANGUAGE="en")
        self.assertEqual(r.status_code, 200)

    def test_muscat_grape_has_description_and_markers(self):
        g = Grape.objects.get(slug="muscat-a-petits-grains")
        self.assertIn("linalol", g.description)
        r = self.client.get(g.get_absolute_url())
        names = [m["molecule"].slug for m in r.context["markers"]]
        self.assertEqual(names[0], "linalol")
