import json
from datetime import timedelta
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.analytics import stats
from apps.analytics.models import Event, PageView
from apps.analytics.tracking import classify, parse_ua, purge
from apps.blindtest.models import Game

CHROME = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/130.0 Safari/537.36")
TIKTOK = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
          "Mobile/15E148 musical_ly_37.5.0 JsSdk/2.0 NetType/WIFI Channel/App Store ByteLocale/fr")
INSTAGRAM = ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 "
             "Mobile Safari/537.36 Instagram 350.0.0.0 Android")


class ParsingTests(TestCase):
    def test_in_app_browsers_are_recognised_without_referrer(self):
        self.assertEqual(classify("", TIKTOK, ""), "tiktok")
        self.assertEqual(classify("", INSTAGRAM, ""), "instagram")
        self.assertEqual(parse_ua(TIKTOK)[:2], ("mobile", "tiktok (appli)"))

    def test_utm_wins_then_referrer_then_direct(self):
        self.assertEqual(classify("Newsletter", TIKTOK, "google.fr"), "newsletter")
        self.assertEqual(classify("", CHROME, "google.fr"), "google")
        self.assertEqual(classify("", CHROME, "t.co"), "x")
        self.assertEqual(classify("", CHROME, "blog.exemple.fr"), "autre site")
        self.assertEqual(classify("", CHROME, ""), "direct")
        self.assertEqual(parse_ua(CHROME), ("ordinateur", "Chrome", "Windows"))


class PageViewTests(TestCase):
    def get(self, url, ua=CHROME, **extra):
        return self.client.get(url, HTTP_USER_AGENT=ua, **extra)

    def test_page_is_recorded_with_its_source_and_campaign(self):
        self.get("/blind-test/?utm_source=tiktok&utm_campaign=devine-le-vin", ua=TIKTOK)
        pv = PageView.objects.get()
        self.assertEqual((pv.path, pv.source, pv.utm_campaign, pv.device), ("/blind-test/", "tiktok",
                                                                            "devine-le-vin", "mobile"))
        self.assertTrue(pv.is_entry)
        self.get("/catalogue/", ua=TIKTOK)
        second = PageView.objects.latest("created_at")
        self.assertFalse(second.is_entry)
        self.assertEqual(second.visitor, pv.visitor)  # même visiteur du jour, sans cookie
        self.assertEqual(second.source, "")

    def test_no_ip_is_stored_and_visitors_differ(self):
        self.get("/", REMOTE_ADDR="1.2.3.4")
        self.get("/", REMOTE_ADDR="5.6.7.8")
        a, b = PageView.objects.all()
        self.assertNotEqual(a.visitor, b.visitor)
        for f in PageView._meta.get_fields():
            self.assertNotIn("1.2.3.4", str(getattr(a, f.name, "")))

    def test_bots_htmx_fragments_admin_and_refusals_are_ignored(self):
        self.get("/", ua="Googlebot/2.1 (+http://www.google.com/bot.html)")
        self.get("/", ua="")
        self.get("/", HTTP_DNT="1")
        self.get("/", HTTP_SEC_GPC="1")
        self.get("/catalogue/", HTTP_HX_REQUEST="true")
        self.get("/admin/login/")
        self.get("/robots.txt")
        self.assertEqual(PageView.objects.count(), 0)

    def test_staff_is_not_counted_unless_asked(self):
        staff = User.objects.create_user("equipe", password="x", is_staff=True)
        self.client.force_login(staff)
        self.get("/")
        self.assertEqual(PageView.objects.count(), 0)
        self.assertEqual(self.client.cookies["terroirs_ne_pas_compter"].value, "1")
        del self.client.cookies["terroirs_ne_pas_compter"]
        with override_settings(ANALYTICS_TRACK_STAFF=True):
            self.get("/")
        self.assertEqual(PageView.objects.get().user, staff)

    def test_a_device_can_be_excluded_and_its_visits_erased(self):
        self.get("/")
        self.get("/catalogue/")
        self.assertEqual(PageView.objects.count(), 2)
        res = self.client.post("/stats/ne-pas-me-compter/", {"action": "ignorer"}, HTTP_USER_AGENT=CHROME)
        self.assertContains(res, "n'est pas compté")
        self.assertEqual(PageView.objects.count(), 0)
        self.get("/")
        self.assertEqual(PageView.objects.count(), 0)
        self.client.post("/stats/ne-pas-me-compter/", {"action": "compter"}, HTTP_USER_AGENT=CHROME)
        self.get("/")
        self.assertEqual(PageView.objects.count(), 1)

    def test_staff_devices_stay_excluded_after_logout(self):
        staff = User.objects.create_user("equipe", password="x", is_staff=True)
        self.client.force_login(staff)
        self.get("/")
        self.client.post("/compte/deconnexion/", HTTP_USER_AGENT=CHROME)  # logout() du client vide les cookies
        self.assertFalse(self.client.session.get("_auth_user_id"))
        self.get("/")
        self.assertEqual(PageView.objects.count(), 0)

    def test_not_found_pages_are_recorded(self):
        self.get("/nexiste-pas/")
        self.assertEqual(PageView.objects.get().status, 404)

    @override_settings(ANALYTICS_ENABLED=False)
    def test_can_be_switched_off(self):
        self.get("/")
        self.assertEqual(PageView.objects.count(), 0)

    def test_engagement_beacon_completes_the_last_view(self):
        self.get("/catalogue/")
        body = json.dumps({"p": "/catalogue/", "t": 42_000, "s": 80})
        res = self.client.post("/stats/engagement/", body, content_type="application/json", HTTP_USER_AGENT=CHROME)
        self.assertEqual(res.status_code, 204)
        pv = PageView.objects.get()
        self.assertEqual((pv.engaged_ms, pv.scroll), (42_000, 80))
        bad = self.client.post("/stats/engagement/", "nope", content_type="application/json", HTTP_USER_AGENT=CHROME)
        self.assertEqual(bad.status_code, 400)

    def test_old_data_is_purged(self):
        self.get("/")
        PageView.objects.update(day=timezone.localdate() - timedelta(days=400))
        Event.objects.create(day=timezone.localdate() - timedelta(days=400), visitor="x", name="old")
        self.assertEqual(purge(), 2)


class EventTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())

    def test_blind_test_start_and_abandon_are_tracked(self):
        self.client.post("/blind-test/nouvelle-partie/", {"mode": "free"}, HTTP_USER_AGENT=CHROME)
        game = Game.objects.get()
        start = Event.objects.get(name="blindtest_start")
        self.assertEqual(start.props["wine"], game.profile.slug)
        self.client.post(f"/blind-test/partie/{game.public_id}/abandon/", HTTP_USER_AGENT=CHROME)
        self.client.post(f"/blind-test/partie/{game.public_id}/abandon/", HTTP_USER_AGENT=CHROME)
        self.assertEqual(Event.objects.filter(name="blindtest_abandoned").count(), 1)  # une seule fin

    def test_login_is_tracked_and_counted(self):
        User.objects.create_user("membre", password="Vin-de-garde-2026")
        self.client.post("/compte/connexion/", {"username": "membre", "password": "Vin-de-garde-2026"},
                         HTTP_USER_AGENT=CHROME)
        self.assertEqual(Event.objects.filter(name="login").count(), 1)
        self.client.get("/", HTTP_USER_AGENT=CHROME)
        kpis = {k["label"]: k["value"] for k in stats.dashboard("7")["kpis"]}
        self.assertEqual((kpis["Connexions"], kpis["Membres actifs"]), (1, 1))

    def test_signup_is_tracked(self):
        self.client.post("/compte/inscription/", {"username": "nouveau", "email": "n@exemple.fr", "adult": "on",
                                                  "password": "Vin-de-garde-2026"}, HTTP_USER_AGENT=CHROME)
        self.assertTrue(User.objects.filter(username="nouveau").exists())
        self.assertTrue(Event.objects.filter(name="signup").exists())


class DashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())

    def setUp(self):
        for ua, url in ((TIKTOK, "/blind-test/"), (TIKTOK, "/catalogue/"), (INSTAGRAM, "/"), (CHROME, "/carte/")):
            self.client.get(url, HTTP_USER_AGENT=ua)
        self.client.post("/blind-test/nouvelle-partie/", {"mode": "free"}, HTTP_USER_AGENT=TIKTOK)

    def test_figures(self):
        data = stats.dashboard("7")
        kpis = {k["label"]: k["value"] for k in data["kpis"]}
        self.assertEqual(kpis["Visiteurs"], 3)
        self.assertEqual(kpis["Parties de blind test"], 1)
        tiktok = next(s for s in data["sources"] if s["label"] == "tiktok")
        self.assertEqual((tiktok["visits"], tiktok["per_visit"], tiktok["play"]), (1, 2.0, 100))
        self.assertEqual(data["funnel"][0]["n"], 1)

    def test_only_staff_can_see_it(self):
        self.assertEqual(self.client.get("/admin/statistiques/").status_code, 302)
        admin = User.objects.create_superuser("admin", "a@exemple.fr", "x")
        self.client.force_login(admin)
        res = self.client.get("/admin/statistiques/?p=30")
        self.assertContains(res, "Statistiques de visite")
        self.assertContains(res, "tiktok")
        self.assertContains(self.client.get("/admin/"), "/admin/statistiques/")
        csv = self.client.get("/admin/statistiques/export.csv?p=7")
        self.assertEqual(csv["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("tiktok", csv.content.decode("utf-8-sig"))
