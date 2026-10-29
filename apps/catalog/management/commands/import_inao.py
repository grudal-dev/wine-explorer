"""Enrichit les appellations avec le fichier ouvert de l'INAO.

Source : « Aires et produits AOC/AOP et IGP » (INAO, data.gouv.fr,
Licence Ouverte 2.0). Une ligne par couple aire géographique × commune ×
produit. Téléchargez le CSV puis :

    python manage.py import_inao chemin/vers/fichier.csv
    python manage.py import_inao fichier.csv --dry-run
    python manage.py import_inao fichier.csv --create   # crée les appellations viticoles manquantes

Les noms de colonnes varient selon les millésimes du fichier : la commande
reconnaît plusieurs variantes (voir COLUMNS) et indique celles qu'elle utilise.
"""

import csv
import io
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.catalog.models import Appellation, Country, Region
from apps.catalog.text import normalize

COLUMNS = {
    "area": ["aire geographique", "aire_geographique", "appellation", "nom aire", "aire"],
    "product": ["produit", "denomination", "libelle produit", "produit_libelle"],
    "code": ["ida", "id aire", "id_aire", "id appellation", "id_app", "code aire"],
    "sign": ["signe", "categorie", "type signe", "aoc/aop/igp", "signe de qualite"],
    "commune": ["ci", "code insee", "insee", "commune", "nom commune"],
}
WINE_HINTS = ("vin", "rouge", "blanc", "rose", "mousseux", "cremant", "effervescent", "vdn", "liquoreux")


def _pick(headers: list[str], key: str) -> str | None:
    norm = {normalize(h): h for h in headers}
    for cand in COLUMNS[key]:
        if cand in norm:
            return norm[cand]
    for cand in COLUMNS[key]:
        for n, raw in norm.items():
            if n.startswith(cand):
                return raw
    return None


class _Semicolon(csv.excel):
    delimiter = ";"


def read_rows(path: Path) -> tuple[list[dict], list[str]]:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    sample = text[:5000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
    except csv.Error:
        dialect = _Semicolon
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    rows = list(reader)
    return rows, reader.fieldnames or []


class Command(BaseCommand):
    help = "Importe les identifiants INAO et le nombre de communes des appellations."

    def add_arguments(self, parser):
        parser.add_argument("csv_path")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--create", action="store_true",
                            help="Créer les appellations viticoles absentes (région « À classer »).")

    def handle(self, csv_path, dry_run, create, **opts):
        path = Path(csv_path)
        if not path.exists():
            raise CommandError(f"Fichier introuvable : {path}")
        rows, headers = read_rows(path)
        cols = {k: _pick(headers, k) for k in COLUMNS}
        if not cols["area"]:
            raise CommandError(f"Colonne d'aire géographique introuvable parmi : {headers}")
        self.stdout.write("Colonnes utilisées : " + ", ".join(f"{k}={v}" for k, v in cols.items() if v))

        areas: dict[str, dict] = defaultdict(lambda: {"communes": set(), "codes": set(), "products": set(),
                                                     "signs": set(), "label": ""})
        for row in rows:
            name = (row.get(cols["area"]) or "").strip()
            if not name:
                continue
            a = areas[normalize(name)]
            a["label"] = name
            if cols["commune"] and row.get(cols["commune"]):
                a["communes"].add(row[cols["commune"]].strip())
            if cols["code"] and row.get(cols["code"]):
                a["codes"].add(row[cols["code"]].strip())
            if cols["product"] and row.get(cols["product"]):
                a["products"].add(row[cols["product"]].strip())
            if cols["sign"] and row.get(cols["sign"]):
                a["signs"].add(row[cols["sign"]].strip().upper())

        existing = {normalize(a.name): a for a in Appellation.objects.all()}
        matched = created = 0
        with transaction.atomic():
            for key, info in areas.items():
                app = existing.get(key)
                if app is None:
                    if not create or not self._is_wine(info):
                        continue
                    app = self._create(info)
                    created += 1
                app.inao_code = sorted(info["codes"])[0] if info["codes"] else app.inao_code
                app.communes_count = len(info["communes"]) or app.communes_count
                if "IGP" in info["signs"] and app.classification == "AOC" and not app.profiles.exists():
                    app.classification = "IGP"
                app.source = "inao"
                app.save()
                matched += 1
            if dry_run:
                transaction.set_rollback(True)
        missing = [a.name for k, a in existing.items() if k not in areas]
        self.stdout.write(self.style.SUCCESS(
            f"{len(areas)} aires lues, {matched} appellations enrichies, {created} créées"
            + (" (simulation)" if dry_run else "") + "."
        ))
        if missing:
            sample = ", ".join(sorted(missing)[:30])
            self.stdout.write(f"Sans correspondance dans le fichier ({len(missing)}) : {sample}")

    def _is_wine(self, info) -> bool:
        text = normalize(" ".join(info["products"]))
        return any(h in text for h in WINE_HINTS)

    def _create(self, info) -> Appellation:
        country, _ = Country.objects.get_or_create(code="FR", defaults={"name": "France", "slug": "france"})
        bucket, _ = Region.objects.get_or_create(
            slug="a-classer", defaults={"name": "À classer", "country": country,
                                        "description": "Appellations importées en attente de rattachement."},
        )
        return Appellation.objects.create(
            name=info["label"], slug=slugify(info["label"])[:180], country=country, region=bucket,
            classification="IGP" if "IGP" in info["signs"] else "AOC", source="inao",
        )
