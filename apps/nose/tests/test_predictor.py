from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import Aroma, AromaFamily
from apps.nose.predictor import predict


def ids(*names):
    return [Aroma.objects.get(name=n).id for n in names]


class PredictorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())

    def top(self, *names, **kw):
        return [r["profile"]["name"] for r in predict(ids(*names), **kw)["results"]]

    def test_classic_profiles(self):
        self.assertEqual(self.top("cassis", "cèdre", "graphite")[0], "Pauillac rouge")
        self.assertEqual(self.top("litchi", "rose")[0], "Alsace gewurztraminer")
        self.assertEqual(self.top("noix", "curry")[0], "Château-Chalon blanc")
        self.assertIn(self.top("silex", "pamplemousse", "buis")[0], {"Sancerre blanc", "Pouilly-Fumé blanc"})

    def test_probabilities(self):
        res = predict(ids("cassis", "violette"))["results"]
        self.assertEqual(len(res), 5)
        probs = [r["probability"] for r in res]
        self.assertEqual(probs, sorted(probs, reverse=True))
        self.assertLessEqual(sum(probs), 1.0001)

    def test_color_filter_and_family(self):
        fam = AromaFamily.objects.get(name="Fruits rouges")
        res = predict([], [fam.id], colors=["rose"])["results"]
        self.assertTrue(res)
        self.assertTrue(all(r["profile"]["color"] == "rose" for r in res))

    def test_empty(self):
        self.assertEqual(predict([])["results"], [])

    def test_views(self):
        self.assertEqual(self.client.get(reverse("nose:nose")).status_code, 200)
        r = self.client.get(reverse("nose:nose"), {"q": "cassis, cèdre, xyzzy"})
        self.assertContains(r, "Pauillac rouge")
        self.assertContains(r, "xyzzy")
        r = self.client.get(reverse("nose:nose"), {"a": ids("litchi")}, HTTP_HX_REQUEST="true")
        self.assertContains(r, "gewurztraminer")
        self.assertNotContains(r, "<html")
        r = self.client.get(reverse("nose:api_aromas"), {"q": "fruits rou"})
        self.assertEqual(r.json()["results"][0]["kind"], "family")


class SensoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_seed", stdout=StringIO())

    def top(self, aromas=(), senses=(), **kw):
        return [r["profile"]["name"] for r in predict(ids(*aromas), senses=list(senses), **kw)["results"]]

    def test_mouth_alone_is_enough(self):
        self.assertTrue(all("Champagne" in n or "Crémant" in n for n in self.top(senses=["bulles"])[:3]))
        sweet = {"Monbazillac blanc", "Sauternes blanc", "Coteaux du Layon blanc"}
        self.assertIn(self.top(["miel"], ["liquoreux"])[0], sweet)

    def test_mouth_reorders_aromas(self):
        light = self.top(["cassis"], ["leger", "tanins-soyeux"])
        big = self.top(["cassis"], ["puissant", "astringent"])
        self.assertNotEqual(light[0], big[0])
        self.assertIn("Pauillac rouge", big[:3])

    def test_one_term_per_axis(self):
        from apps.nose import sensory
        self.assertEqual([t.key for t in sensory.clean(["leger", "vif", "puissant"])], ["puissant", "vif"])

    def test_explanations(self):
        res = predict(ids("cassis"), senses=["tannique"])["results"][0]
        sense = [m for m in res["matches"] if m.get("sense")][0]
        self.assertEqual(sense["name"], "tannique")
        self.assertIn("tanins", sense["actual"])

    def test_free_text_and_api(self):
        r = self.client.get(reverse("nose:nose"), {"q": "litchi, nerveux, pétillant"})
        self.assertContains(r, 'name="s" value="vif"')
        self.assertContains(r, 'name="s" value="bulles"')
        api = self.client.get(reverse("nose:api_aromas"), {"q": "tanni"}).json()["results"]
        self.assertIn("sense", {x["kind"] for x in api})
        self.assertEqual(self.client.get(reverse("nose:api_aromas"), {"q": "vif"}).json()["results"][0]["pk"], "vif")
