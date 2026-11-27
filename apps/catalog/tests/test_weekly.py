from datetime import date, timedelta
from io import StringIO
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.blindtest.engine import daily_profile
from apps.catalog import weekly

QUIET = date(2026, 12, 9)  # mercredi sans fête


class WineOfTheWeekTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", country="all", skip_molecules=True, stdout=StringIO())

    def setUp(self):
        cache.clear()

    def _get(self, day, path="/"):
        with mock.patch("apps.catalog.seasons.timezone.localdate", return_value=day):
            return self.client.get(path).content.decode()

    def test_same_wine_all_week(self):
        monday = QUIET - timedelta(days=QUIET.weekday())
        slugs = {weekly.pick_slug(monday + timedelta(days=i)) for i in range(7)}
        self.assertEqual(len(slugs), 1)

    def test_no_repeat_within_a_year(self):
        picks = [weekly.pick_slug(date(2027, 1, 4) + timedelta(weeks=k)) for k in range(52)]
        self.assertEqual(len(picks), len(set(picks)))

    def test_never_a_daily_challenge_of_the_week(self):
        for k in range(12):
            day = QUIET + timedelta(weeks=k)
            _y, _w, monday = weekly.week_of(day)
            daily = {daily_profile(monday + timedelta(days=i)).slug for i in range(7)}
            self.assertNotIn(weekly.pick_slug(day), daily)

    def test_banner_when_no_festival(self):
        html = self._get(QUIET)
        slug = weekly.pick_slug(QUIET)
        self.assertIn('class="weekly"', html)
        self.assertIn(f'href="/catalogue/vins/{slug}/"', html)
        self.assertIn(f"?depart=profile:{slug}", html)

    def test_festival_takes_the_banner(self):
        html = self._get(date(2026, 11, 20))  # Beaujolais nouveau
        self.assertIn("decor-beaujolais", html)
        self.assertNotIn('class="weekly"', html)

    def test_hidden_on_game_pages(self):
        self.assertNotIn('class="weekly"', self._get(QUIET, "/blind-test/"))
        self.assertNotIn('class="weekly"', self._get(QUIET, "/chaud-froid/"))

    @override_settings(WINE_OF_THE_WEEK=False)
    def test_can_be_turned_off(self):
        self.assertNotIn('class="weekly"', self._get(QUIET))

    def test_english(self):
        self.assertIn("Wine of the week", self._get(QUIET, "/en/"))

    def test_only_on_home(self):
        # Un seul encart éditorial, sur l'accueil : il ne retarde pas les autres pages.
        self.assertNotIn('class="weekly"', self._get(QUIET, "/catalogue/"))
