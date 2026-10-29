"""Relie appellations et cépages à Wikidata (CC0) et complète les coordonnées.

    python manage.py import_wikidata              # appellations et cépages sans identifiant
    python manage.py import_wikidata --dry-run
    python manage.py import_wikidata --only grapes

Utilise l'API publique wbsearchentities / wbgetentities. Un résultat n'est
retenu que si sa description évoque le vin (appellation) ou le cépage, pour
éviter de relier « Margaux » à la commune ou à une personne.
"""

import json
import time
import urllib.parse
import urllib.request

from django.core.management.base import BaseCommand

from apps.catalog.models import Appellation, Grape
from apps.catalog.text import normalize

API = "https://www.wikidata.org/w/api.php"
UA = "Terroirs/0.1 (application pédagogique sur le vin)"
APPELLATION_HINTS = ("vin", "wine", "appellation", "aoc", "aop", "vignoble")
GRAPE_HINTS = ("cepage", "grape", "variety", "vitis")


def _get(params: dict) -> dict:
    url = f"{API}?{urllib.parse.urlencode({**params, 'format': 'json'})}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as res:
        return json.load(res)


def search(label: str, hints: tuple[str, ...]) -> str | None:
    for lang in ("fr", "en"):
        data = _get({"action": "wbsearchentities", "search": label, "language": lang,
                     "uselang": lang, "type": "item", "limit": 7})
        for hit in data.get("search", []):
            desc = normalize(hit.get("description", ""))
            if any(h in desc for h in hints):
                return hit["id"]
    return None


def coordinates(qid: str) -> tuple[float, float] | None:
    data = _get({"action": "wbgetentities", "ids": qid, "props": "claims"})
    claims = data.get("entities", {}).get(qid, {}).get("claims", {})
    for claim in claims.get("P625", []):
        v = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if v:
            return v["latitude"], v["longitude"]
    return None


class Command(BaseCommand):
    help = "Associe les identifiants Wikidata aux appellations et cépages."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--only", choices=["appellations", "grapes"])
        parser.add_argument("--pause", type=float, default=0.3, help="Pause entre requêtes (s).")

    def handle(self, dry_run, only, pause, **opts):
        if only != "grapes":
            for app in Appellation.objects.filter(wikidata_id=""):
                qid = search(f"{app.name}", APPELLATION_HINTS) or search(f"{app.name} AOC", APPELLATION_HINTS)
                self._report(app, qid)
                if qid and not dry_run:
                    app.wikidata_id = qid
                    if app.lat is None and (c := coordinates(qid)):
                        app.lat, app.lng = c
                    app.save()
                time.sleep(pause)
        if only != "appellations":
            for grape in Grape.objects.filter(wikidata_id=""):
                qid = search(grape.name, GRAPE_HINTS)
                self._report(grape, qid)
                if qid and not dry_run:
                    grape.wikidata_id = qid
                    grape.save(update_fields=["wikidata_id"])
                time.sleep(pause)

    def _report(self, obj, qid):
        if qid:
            self.stdout.write(f"  {obj.name} → {qid}")
        else:
            self.stdout.write(self.style.WARNING(f"  {obj.name} : aucun résultat fiable"))
