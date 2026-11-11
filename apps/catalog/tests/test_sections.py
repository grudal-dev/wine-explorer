from django.test import TestCase, override_settings


class SectionGateTests(TestCase):
    def test_everything_served_by_default(self):
        self.assertEqual(self.client.get("/graphe/").status_code, 200)

    @override_settings(PUBLIC_SECTIONS=["molecules", "carte", "catalogue"])
    def test_partial_deploy(self):
        self.assertEqual(self.client.get("/molecules/").status_code, 200)
        self.assertEqual(self.client.get("/carte/").status_code, 200)
        self.assertEqual(self.client.get("/catalogue/").status_code, 200)
        for path in ("/graphe/", "/blind-test/", "/le-nez/", "/compte/connexion/"):
            self.assertEqual(self.client.get(path).status_code, 404, path)
        root = self.client.get("/")
        self.assertRedirects(root, "/molecules/", fetch_redirect_response=False)

    @override_settings(PUBLIC_SECTIONS=["molecules", "carte", "catalogue"])
    def test_menu_hides_disabled_sections(self):
        html = self.client.get("/molecules/").content.decode()
        self.assertNotIn('href="/graphe/"', html)
        self.assertNotIn('href="/blind-test/"', html)
        self.assertNotIn('href="/compte/', html)
        self.assertIn('href="/carte/"', html)

    @override_settings(PUBLIC_SECTIONS=["molecules", "typo"])
    def test_unknown_section_is_an_error(self):
        from django.core.exceptions import ImproperlyConfigured

        with self.assertRaises(ImproperlyConfigured):
            self.client.get("/molecules/")
