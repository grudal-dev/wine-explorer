from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.pages.models import ContactMessage


class InfoPagesTests(TestCase):
    def test_pages_are_served_and_linked(self):
        for name in ("about", "legal", "privacy", "contact"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        footer = self.client.get("/catalogue/").content.decode()
        for path in ("/a-propos/", "/mentions-legales/", "/confidentialite/", "/contact/"):
            self.assertIn(f'href="{path}"', footer)

    @override_settings(LEGAL_PUBLISHER="Lucas Exemple", LEGAL_DIRECTOR="", CONTACT_EMAIL="bonjour@exemple.fr")
    def test_legal_names_publisher_and_host(self):
        html = self.client.get(reverse("legal")).content.decode()
        self.assertIn("Lucas Exemple", html)
        self.assertIn("Railway Corporation", html)
        self.assertIn("mailto:bonjour@exemple.fr", html)

    def test_legal_without_publisher_uses_lcen_anonymity(self):
        self.assertContains(self.client.get(reverse("legal")), "LCEN")

    def test_english(self):
        self.assertContains(self.client.get("/en/confidentialite/"), "No cookie is used to measure the audience")

    @override_settings(SITE_NAME="Nez Libre")
    def test_site_name_setting(self):
        html = self.client.get("/catalogue/").content.decode()
        self.assertIn("Nez Libre", html)
        self.assertNotIn("Wine Explorer", html)


class ContactTests(TestCase):
    DATA = {"topic": "error", "email": "a@exemple.fr", "message": "Le Tokaj est mal décrit."}

    def test_message_is_stored(self):
        r = self.client.post(reverse("contact"), self.DATA)
        self.assertRedirects(r, reverse("contact_sent"))
        self.assertEqual(ContactMessage.objects.get().topic, "error")

    def test_honeypot_drops_robots(self):
        self.client.post(reverse("contact"), {**self.DATA, "website": "http://spam"})
        self.assertFalse(ContactMessage.objects.exists())

    def test_rate_limited(self):
        for _ in range(6):
            self.client.post(reverse("contact"), self.DATA)
        self.assertEqual(ContactMessage.objects.count(), 5)


class AccountDeletionTests(TestCase):
    def test_delete_requires_password(self):
        User.objects.create_user("eve", "e@exemple.fr", "Un-Bon-Cru-2026")
        self.client.login(username="eve", password="Un-Bon-Cru-2026")
        self.client.post(reverse("accounts:delete"), {"password": "faux"})
        self.assertTrue(User.objects.filter(username="eve").exists())
        self.client.post(reverse("accounts:delete"), {"password": "Un-Bon-Cru-2026"})
        self.assertFalse(User.objects.filter(username="eve").exists())


class SignupTests(TestCase):
    def test_signup_returns_to_the_game(self):
        r = self.client.post(reverse("accounts:signup") + "?next=/blind-test/",
                             {"username": "zoe", "email": "z@exemple.fr", "password": "Un-Bon-Cru-2026",
                              "adult": "on", "next": "/blind-test/"})
        self.assertRedirects(r, "/blind-test/", fetch_redirect_response=False)

    def test_external_next_is_ignored(self):
        r = self.client.post(reverse("accounts:signup"),
                             {"username": "zoe", "email": "z@exemple.fr", "password": "Un-Bon-Cru-2026",
                              "adult": "on", "next": "https://ailleurs.example/"})
        self.assertRedirects(r, reverse("accounts:profile"), fetch_redirect_response=False)

    def test_weak_password_refused(self):
        self.client.post(reverse("accounts:signup"),
                         {"username": "zoe", "email": "z@exemple.fr", "password": "12345678", "adult": "on"})
        self.assertFalse(User.objects.filter(username="zoe").exists())
