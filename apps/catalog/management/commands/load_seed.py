"""Charge (ou recharge) le jeu de données de référence livré avec le projet.

    python manage.py load_seed            # France
    python manage.py load_seed --check    # valide les YAML sans écrire

La commande est idempotente : elle met à jour les objets existants (clé :
slug) et remplace les encépagements et arômes des profils. Toute référence
inconnue (cépage, arôme, région) fait échouer le chargement, pour garder
des données propres.
"""

from pathlib import Path

import yaml
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.catalog.models import (
    Appellation,
    Aroma,
    AromaFamily,
    Color,
    Country,
    Grape,
    ProfileAroma,
    ProfileGrape,
    Region,
    Style,
    WineProfile,
)
from apps.catalog.text import normalize

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

PROFILE_KEYS = {
    "name", "color", "style", "grapes", "aromas", "structure", "price", "aging",
    "temp", "pairings", "description",
}
APPELLATION_KEYS = {"appellation", "region", "classification", "lat", "lng", "profiles", "description"}


class Command(BaseCommand):
    help = "Charge le jeu de données de référence (régions, cépages, arômes, appellations, profils)."

    def add_arguments(self, parser):
        parser.add_argument("--country", default="fr", help="Dossier de données (défaut : fr).")
        parser.add_argument("--check", action="store_true", help="Valider sans écrire en base.")

    def handle(self, *args, country, check, **options):
        folder = DATA_DIR / country
        if not folder.is_dir():
            raise CommandError(f"Dossier de données introuvable : {folder}")
        try:
            with transaction.atomic():
                stats = self._load(folder)
                if check:
                    transaction.set_rollback(True)
        except (KeyError, ValueError) as exc:
            raise CommandError(f"Données invalides : {exc}") from exc
        if not check:
            from django.core.cache import cache

            from apps.catalog import index
            from apps.explorer import graph
            from apps.nose import predictor

            cache.clear()
            index.reset()
            graph.reset()
            predictor.reset()
        verb = "validé" if check else "chargé"
        self.stdout.write(self.style.SUCCESS(
            f"Jeu de données {verb} : " + ", ".join(f"{v} {k}" for k, v in stats.items())
        ))

    # ------------------------------------------------------------------
    def _read(self, path: Path):
        with path.open(encoding="utf-8") as fh:
            return yaml.safe_load(fh)

    def _load(self, folder: Path) -> dict:
        regions_doc = self._read(folder / "regions.yaml")
        c = regions_doc["country"]
        country, _ = Country.objects.update_or_create(
            code=c["code"], defaults={"name": c["name"], "slug": slugify(c["name"])}
        )

        regions: dict[str, Region] = {}
        for item in regions_doc["regions"]:
            parent = self._region(country, item, None, Region.Kind.REGION)
            regions[parent.name] = parent
            for child in item.get("children", []):
                regions[child["name"]] = self._region(country, child, parent, Region.Kind.SUBREGION)

        grapes = self._load_grapes(folder / "grapes.yaml")
        aromas = self._load_aromas(folder / "aromas.yaml")

        n_app = n_prof = 0
        for path in sorted(folder.glob("appellations_*.yaml")):
            for entry in self._read(path) or []:
                unknown = set(entry) - APPELLATION_KEYS
                if unknown:
                    raise ValueError(f"{path.name} · {entry.get('appellation')}: clés inconnues {unknown}")
                if entry["region"] not in regions:
                    raise KeyError(f"région inconnue « {entry['region']} » ({entry['appellation']})")
                colors = sorted({p["color"] for p in entry["profiles"]})
                app, _ = Appellation.objects.update_or_create(
                    slug=slugify(entry["appellation"]),
                    defaults={
                        "name": entry["appellation"],
                        "country": country,
                        "region": regions[entry["region"]],
                        "classification": entry.get("classification", "AOC"),
                        "colors": colors,
                        "lat": entry.get("lat"),
                        "lng": entry.get("lng"),
                        "description": entry.get("description", ""),
                    },
                )
                n_app += 1
                for prof in entry["profiles"]:
                    self._profile(app, prof, grapes, aromas, path.name)
                    n_prof += 1

        return {
            "régions": len(regions),
            "cépages": len(set(grapes.values())),
            "arômes": len(set(aromas.values())),
            "appellations": n_app,
            "profils": n_prof,
        }

    def _region(self, country, item, parent, kind) -> Region:
        region, _ = Region.objects.update_or_create(
            slug=slugify(item["name"]),
            defaults={
                "name": item["name"],
                "country": country,
                "parent": parent,
                "kind": kind,
                "lat": item.get("lat"),
                "lng": item.get("lng"),
                "description": item.get("description", ""),
            },
        )
        return region

    def _load_grapes(self, path: Path) -> dict[str, Grape]:
        lookup: dict[str, Grape] = {}
        for item in self._read(path):
            grape, _ = Grape.objects.update_or_create(
                slug=slugify(item["name"]),
                defaults={
                    "name": item["name"],
                    "skin": item["skin"],
                    "origin": item.get("origin", ""),
                    "synonyms": item.get("synonyms", []),
                },
            )
            for label in [item["name"], *item.get("synonyms", [])]:
                lookup[normalize(label)] = grape
        return lookup

    def _load_aromas(self, path: Path) -> dict[str, Aroma]:
        lookup: dict[str, Aroma] = {}
        for order, fam in enumerate(self._read(path)["families"]):
            family, _ = AromaFamily.objects.update_or_create(
                slug=slugify(fam["name"]),
                defaults={"name": fam["name"], "order": order, "color": fam["color"]},
            )
            for item in fam["aromas"]:
                aroma, _ = Aroma.objects.update_or_create(
                    slug=slugify(item["name"]),
                    defaults={
                        "name": item["name"],
                        "family": family,
                        "synonyms": item.get("synonyms", []),
                    },
                )
                for label in [item["name"], *item.get("synonyms", [])]:
                    lookup[normalize(label)] = aroma
        return lookup

    def _profile(self, app, prof, grapes, aromas, source):
        unknown = set(prof) - PROFILE_KEYS
        if unknown:
            raise ValueError(f"{source} · {app.name}: clés inconnues {unknown}")
        color = prof["color"]
        if color not in Color.values:
            raise ValueError(f"{app.name}: couleur inconnue {color}")
        style = prof.get("style", Style.TRANQUILLE)
        if style not in Style.values:
            raise ValueError(f"{app.name}: style inconnu {style}")
        name = prof.get("name") or f"{app.name} {Color(color).label.lower()}"
        body, acidity, tannin, sweetness = prof["structure"]
        price = prof.get("price") or [None, None]
        aging = prof.get("aging") or [None, None]

        profile, _ = WineProfile.objects.update_or_create(
            slug=slugify(name),
            defaults={
                "name": name,
                "appellation": app,
                "color": color,
                "style": style,
                "body": body,
                "acidity": acidity,
                "tannin": tannin,
                "sweetness": sweetness,
                "price_min": price[0],
                "price_max": price[1],
                "aging_min": aging[0],
                "aging_max": aging[1],
                "serving_temp": str(prof.get("temp", "")),
                "pairings": prof.get("pairings", []),
                "description": prof.get("description", "").strip(),
            },
        )

        profile.profile_grapes.all().delete()
        shares = prof["grapes"]
        if sum(shares.values()) != 100:
            raise ValueError(f"{name}: l'encépagement doit totaliser 100 % ({sum(shares.values())})")
        for label, share in shares.items():
            grape = grapes.get(normalize(label))
            if grape is None:
                raise KeyError(f"cépage inconnu « {label} » ({name})")
            ProfileGrape.objects.create(profile=profile, grape=grape, share=share)

        profile.profile_aromas.all().delete()
        seen = set()
        for label, intensity in prof["aromas"].items():
            aroma = aromas.get(normalize(label))
            if aroma is None:
                raise KeyError(f"arôme inconnu « {label} » ({name})")
            if intensity not in (1, 2, 3):
                raise ValueError(f"{name}: intensité invalide pour {label} ({intensity})")
            if aroma.pk in seen:
                raise ValueError(f"{name}: arôme en double {label}")
            seen.add(aroma.pk)
            ProfileAroma.objects.create(profile=profile, aroma=aroma, intensity=intensity)
