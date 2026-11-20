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


class PerceeTests(TestCase):
    def _get(self, day, path="/catalogue/"):
        with mock.patch("apps.catalog.seasons.timezone.localdate", return_value=day):
            return self.client.get(path).content.decode()

    def test_window(self):
        self.assertEqual(seasons.current_decor(date(2027, 1, 26)), "")
        self.assertEqual(seasons.current_decor(date(2027, 1, 27)), "vinjaune")  # J-10
        self.assertEqual(seasons.current_decor(date(2027, 2, 7)), "vinjaune")
        self.assertEqual(seasons.current_decor(date(2027, 2, 8)), "")
        self.assertEqual(seasons.current_decor(date(2025, 2, 1)), "")  # pas d'édition en 2025

    def test_editions_are_weekends(self):
        for year, e in seasons.PERCEE_EDITIONS.items():
            self.assertEqual((e.start.weekday(), e.end.weekday()), (5, 6), year)
            self.assertEqual(e.end - e.start, seasons.timedelta(days=1), year)

    def test_banner_before_the_weekend(self):
        html = self._get(date(2027, 2, 1))
        self.assertIn("decor-vinjaune", html)
        self.assertIn("6 et 7 février 2027 · Arlay", html)
        self.assertIn("millésime 2020", html)
        self.assertIn("terroirs_percee_2027", html)
        self.assertIn('href="/catalogue/appellations/chateau-chalon/"', html)
        self.assertIn('href="/catalogue/cepages/savagnin/"', html)
        self.assertIn('href="/molecules/sotolon/"', html)

    def test_banner_during_the_weekend(self):
        self.assertIn("Ce week-end · Arlay", self._get(date(2027, 2, 6)))

    def test_english(self):
        html = self._get(date(2027, 2, 1), "/en/catalogue/")
        self.assertIn("Percée du Vin Jaune", html)
        self.assertIn("6 and 7 February 2027 · Arlay", html)

    def test_calendar_reminder(self):
        with mock.patch("apps.catalog.seasons.timezone.localdate", return_value=date(2027, 11, 10)):
            self.assertEqual([w.id for w in seasons.check_percee_calendar(None)], ["catalog.W002"])
        with mock.patch("apps.catalog.seasons.timezone.localdate", return_value=date(2026, 11, 20)):
            self.assertEqual(seasons.check_percee_calendar(None), [])
        with mock.patch("apps.catalog.seasons.timezone.localdate", return_value=date(2027, 6, 1)):
            self.assertEqual(seasons.check_percee_calendar(None), [])
