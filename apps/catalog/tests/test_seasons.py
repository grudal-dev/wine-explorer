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
    def _get(self, day, path="/"):
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
        html = self._get(date(2026, 11, 20), "/en/")
        self.assertIn("Beaujolais Nouveau", html)


class PerceeTests(TestCase):
    def _get(self, day, path="/"):
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
        html = self._get(date(2027, 2, 1), "/en/")
        self.assertIn("Percée du Vin Jaune", html)
        self.assertIn("6 and 7 February 2027 · Arlay", html)

    def test_calendar_reminder(self):
        with mock.patch("apps.catalog.seasons.timezone.localdate", return_value=date(2027, 11, 10)):
            self.assertEqual([w.id for w in seasons.check_percee_calendar(None)], ["catalog.W002"])
        with mock.patch("apps.catalog.seasons.timezone.localdate", return_value=date(2026, 11, 20)):
            self.assertEqual(seasons.check_percee_calendar(None), [])
        with mock.patch("apps.catalog.seasons.timezone.localdate", return_value=date(2027, 6, 1)):
            self.assertEqual(seasons.check_percee_calendar(None), [])


class AutumnDecorTests(TestCase):
    def _get(self, day, path="/"):
        with mock.patch("apps.catalog.seasons.timezone.localdate", return_value=day):
            return self.client.get(path).content.decode()

    def test_medoc_window(self):
        self.assertEqual(seasons.medoc_window(2027).start, date(2027, 9, 4))
        self.assertEqual(seasons.current_decor(date(2027, 8, 27)), "")
        self.assertEqual(seasons.current_decor(date(2027, 8, 28)), "medoc")  # J-7
        self.assertEqual(seasons.current_decor(date(2027, 9, 5)), "medoc")
        self.assertEqual(seasons.current_decor(date(2027, 9, 6)), "")

    def test_medoc_estimated(self):
        w = seasons.medoc_window(2029)  # 1er septembre = samedi : course estimée au 8
        self.assertEqual((w.start, w.confirmed), (date(2029, 9, 8), False))
        self.assertIn("Début septembre · Pauillac", self._get(date(2029, 9, 3)))

    def test_medoc_banner(self):
        html = self._get(date(2027, 9, 1))
        self.assertIn("decor-medoc", html)
        self.assertIn("samedi 4 septembre 2027 · Pauillac", html)
        self.assertIn('href="/catalogue/appellations/pauillac/"', html)
        self.assertIn('href="/catalogue/regions/medoc/"', html)
        self.assertIn("Ce week-end · Pauillac", self._get(date(2027, 9, 4)))

    def test_montmartre_window(self):
        self.assertEqual(seasons.montmartre_window(2026), seasons.Window(date(2026, 10, 7), date(2026, 10, 11)))
        estimated = seasons.montmartre_window(2025 + 2)  # 2027 : deuxième samedi = 9 octobre
        self.assertEqual((estimated.start, estimated.end, estimated.confirmed), (date(2027, 10, 6), date(2027, 10, 10), False))
        # La règle retrouve les éditions connues.
        for year, (start, end) in seasons.MONTMARTRE_EDITIONS.items():
            saturday = seasons._weekday_on_or_after(date(year, 10, 1), 5) + seasons.timedelta(weeks=1)
            self.assertEqual((start, end), (saturday - seasons.timedelta(days=3), saturday + seasons.timedelta(days=1)))
        self.assertEqual(seasons.current_decor(date(2026, 9, 30)), "montmartre")
        self.assertEqual(seasons.current_decor(date(2026, 10, 12)), "")

    def test_montmartre_banner(self):
        html = self._get(date(2026, 10, 1))
        self.assertIn("decor-montmartre", html)
        self.assertIn("Du 7 au 11 octobre 2026 · 93e édition", html)
        self.assertIn("Un peu d'histoire", html)
        self.assertIn("1933", html)
        self.assertIn("Cette semaine · 93e édition", self._get(date(2026, 10, 9)))
        self.assertIn("Début octobre · 94e édition", self._get(date(2027, 10, 1)))

    def test_novello(self):
        self.assertEqual(seasons.current_decor(date(2026, 10, 29)), "")
        self.assertEqual(seasons.current_decor(date(2026, 10, 30)), "novello")
        self.assertEqual(seasons.current_decor(date(2026, 11, 9)), "novello")
        self.assertEqual(seasons.current_decor(date(2026, 11, 10)), "")
        html = self._get(date(2026, 10, 30))
        self.assertIn("30 octobre · aujourd'hui · Italie", html)
        self.assertIn('href="/molecules/acetate-disoamyle/"', html)

    def test_no_overlap_over_many_years(self):
        for year in range(2025, 2040):
            day, seen = date(year, 1, 1), []
            while day.year == year:
                d = seasons.current_decor(day)
                if d and (not seen or seen[-1] != d):
                    seen.append(d)
                day += seasons.timedelta(days=1)
            self.assertEqual(len(seen), len(set(seen)), (year, seen))  # chaque décor d'un seul tenant

    def test_english(self):
        self.assertIn("Montmartre Grape Harvest Festival", self._get(date(2026, 10, 1), "/en/"))
        self.assertIn("Médoc Marathon", self._get(date(2027, 9, 1), "/en/"))
        self.assertIn("Vino novello is here", self._get(date(2026, 10, 31), "/en/"))
