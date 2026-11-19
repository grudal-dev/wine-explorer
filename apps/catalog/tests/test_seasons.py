from datetime import date
from unittest import mock

from django.test import TestCase, override_settings

from apps.catalog import seasons


class BeaujolaisDayTests(TestCase):
    def test_third_thursday_of_november(self):
        self.assertEqual(seasons.beaujolais_day(2026), date(2026, 11, 19))
        self.assertEqual(seasons.beaujolais_day(2025), date(2025, 11, 20))
        self.assertEqual(seasons.beaujolais_day(2029), date(2029, 11, 15))  # 1er novembre = jeudi
        self.assertEqual(seasons.beaujolais_day(2024), date(2024, 11, 21))

    def test_window(self):
        self.assertEqual(seasons.current_decor(date(2026, 11, 18)), "")
        self.assertEqual(seasons.current_decor(date(2026, 11, 19)), "beaujolais")
        self.assertEqual(seasons.current_decor(date(2026, 11, 29)), "beaujolais")  # dimanche J+10
        self.assertEqual(seasons.current_decor(date(2026, 11, 30)), "")

    @override_settings(SEASONAL_DECOR="off")
    def test_off(self):
        self.assertEqual(seasons.current_decor(date(2026, 11, 19)), "")

    @override_settings(SEASONAL_DECOR="beaujolais")
    def test_forced(self):
        self.assertEqual(seasons.current_decor(date(2026, 6, 1)), "beaujolais")


class BeaujolaisDecorViewTests(TestCase):
    def _get(self, day, path="/catalogue/"):
        with mock.patch("apps.catalog.seasons.timezone.localdate", return_value=day):
            return self.client.get(path).content.decode()

    def test_banner_in_season(self):
        html = self._get(date(2026, 11, 19))
        self.assertIn("decor-beaujolais", html)
        self.assertIn('id="primeur"', html)
        self.assertIn("terroirs_primeur_2026", html)
        self.assertIn('href="/catalogue/regions/beaujolais/"', html)
        self.assertIn('href="/catalogue/cepages/gamay/"', html)

    def test_no_banner_out_of_season(self):
        html = self._get(date(2026, 12, 5))
        self.assertNotIn("decor-beaujolais", html)
        self.assertNotIn('id="primeur"', html)

    def test_english(self):
        html = self._get(date(2026, 11, 20), "/en/catalogue/")
        self.assertIn("Beaujolais Nouveau", html)
