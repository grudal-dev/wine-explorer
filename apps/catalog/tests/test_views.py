from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import Appellation, Aroma, Grape, Region, WineProfile


class CatalogViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())

    def test_pages(self):
        urls = [
            reverse("home"), reverse("catalog:index"), reverse("catalog:grapes"),
            reverse("catalog:aromas"), reverse("catalog:sources"),
            WineProfile.objects.first().get_absolute_url(),
            Appellation.objects.first().get_absolute_url(),
            Region.objects.first().get_absolute_url(),
            Grape.objects.first().get_absolute_url(),
            Aroma.objects.first().get_absolute_url(),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_unknown_slug_404(self):
        self.assertEqual(self.client.get("/catalogue/vins/inexistant/").status_code, 404)
