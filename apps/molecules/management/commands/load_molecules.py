"""Charge les molécules, les éléments naturels, la bibliographie, puis déduit les liens vin → molécule.

    python manage.py load_molecules           # après load_seed
    python manage.py load_molecules --check   # valide les YAML sans écrire

Comme load_seed, la commande est idempotente et stricte : une référence, un
cépage, un arôme ou un élément naturel inconnu fait échouer le chargement.
"""

import json
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.catalog.models import Aroma, Color, Grape, Style, WineProfile
from apps.catalog.text import normalize
from apps.molecules.models import (
    BASIS_ORDER,
    Basis,
    ChemicalFamily,
    Molecule,
    NaturalSource,
    Occurrence,
    Origin,
    ProfileMolecule,
    Reference,
    slug_for,
)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
MIN_SHARE = 15

MOLECULE_KEYS = {
    "name", "name_en", "synonyms", "family", "origin", "smiles", "odor", "threshold", "refs",
    "aromas", "aroma_ref", "aroma_max", "universal", "description", "wine", "nature",
}
RULE_KEYS = {"grapes", "styles", "colors", "all", "strength", "ref", "min_share"}


class Command(BaseCommand):
    help = "Charge la section Molécules et calcule les liens profils → molécules."

    def add_arguments(self, parser):
        parser.add_argument("--check", action="store_true", help="Valider sans écrire en base.")

    def handle(self, *args, check, **options):
        try:
            with transaction.atomic():
                stats = self._load()
                if check:
                    transaction.set_rollback(True)
        except (KeyError, ValueError) as exc:
            raise CommandError(f"Données invalides : {exc}") from exc
        if not check:
            from django.core.cache import cache

            from apps.molecules import graph

            cache.clear()
            graph.reset()
        verb = "validée" if check else "chargée"
        self.stdout.write(self.style.SUCCESS(
            f"Section Molécules {verb} : " + ", ".join(f"{v} {k}" for k, v in stats.items())
        ))

    # ------------------------------------------------------------------
    @staticmethod
    def _read(name: str):
        with (DATA_DIR / name).open(encoding="utf-8") as fh:
            return yaml.safe_load(fh)

    def _load(self) -> dict:
        refs = self._load_references()
        aromas = {normalize(a.name): a for a in Aroma.objects.all()}
        for a in Aroma.objects.all():
            for syn in a.synonyms:
                aromas.setdefault(normalize(syn), a)
        sources = self._load_sources(aromas)
        computed_path = DATA_DIR / "computed.json"
        computed = json.loads(computed_path.read_text(encoding="utf-8")) if computed_path.exists() else {}

        grapes = {}
        for g in Grape.objects.all():
            for label in [g.name, *g.synonyms]:
                grapes[normalize(label)] = g

        molecules, rules = [], []
        seen_slugs = set()
        for order, item in enumerate(self._read("molecules.yaml")):
            unknown = set(item) - MOLECULE_KEYS
            if unknown:
                raise ValueError(f"{item.get('name')}: clés inconnues {unknown}")
            name = item["name"]
            slug = slug_for(name)
            if slug in seen_slugs:
                raise ValueError(f"molécule en double : {name}")
            seen_slugs.add(slug)
            if item["family"] not in ChemicalFamily.values:
                raise ValueError(f"{name}: famille chimique inconnue {item['family']}")
            if item["origin"] not in Origin.values:
                raise ValueError(f"{name}: origine inconnue {item['origin']}")
            props = computed.get(slug, {})
            mol, _ = Molecule.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "name_en": item["name_en"],
                    "synonyms": item.get("synonyms", []),
                    "family": item["family"],
                    "origin": item["origin"],
                    "smiles": item["smiles"],
                    "formula": props.get("formula", ""),
                    "molar_mass": props.get("molar_mass"),
                    "odor": item["odor"],
                    "threshold": str(item.get("threshold", "")),
                    "description": " ".join(item.get("description", "").split()),
                    "universal": bool(item.get("universal", False)),
                    "order": order,
                },
            )
            mol.references.set([self._ref(refs, k, name) for k in item.get("refs", [])])
            mol_aromas = []
            for label in item.get("aromas", []):
                aroma = aromas.get(normalize(label))
                if aroma is None:
                    raise KeyError(f"arôme inconnu « {label} » ({name})")
                mol_aromas.append(aroma)
            mol.aromas.set(mol_aromas)

            mol.occurrences.all().delete()
            for occ in item.get("nature", []):
                src = sources.get(normalize(occ["source"]))
                if src is None:
                    raise KeyError(f"élément naturel inconnu « {occ['source']} » ({name})")
                Occurrence.objects.create(
                    molecule=mol, source=src, note=occ.get("note", ""),
                    reference=self._ref(refs, occ["ref"], name),
                )

            aroma_ref = item.get("aroma_ref") or (item.get("refs") or [None])[0]
            if mol_aromas and aroma_ref:
                self._ref(refs, aroma_ref, name)
            parsed = []
            for rule in item.get("wine", []):
                unknown = set(rule) - RULE_KEYS
                if unknown:
                    raise ValueError(f"{name}: clés de règle inconnues {unknown}")
                strength = rule.get("strength", 1)
                if strength not in (1, 2, 3):
                    raise ValueError(f"{name}: force invalide {strength}")
                self._ref(refs, rule["ref"], name)
                r = {"strength": strength, "ref": rule["ref"], "min_share": rule.get("min_share", MIN_SHARE)}
                if rule.get("all"):
                    r["all"] = True
                if "grapes" in rule:
                    r["grapes"] = []
                    for label in rule["grapes"]:
                        g = grapes.get(normalize(label))
                        if g is None:
                            raise KeyError(f"cépage inconnu « {label} » ({name})")
                        r["grapes"].append(g.pk)
                if "styles" in rule:
                    bad = set(rule["styles"]) - set(Style.values)
                    if bad:
                        raise ValueError(f"{name}: styles inconnus {bad}")
                    r["styles"] = rule["styles"]
                if "colors" in rule:
                    bad = set(rule["colors"]) - set(Color.values)
                    if bad:
                        raise ValueError(f"{name}: couleurs inconnues {bad}")
                    r["colors"] = rule["colors"]
                parsed.append(r)
            molecules.append(mol)
            rules.append((mol, parsed, {a.pk for a in mol_aromas}, aroma_ref, item.get("aroma_max", 2)))

        Molecule.objects.exclude(slug__in=seen_slugs).delete()
        n_links = self._link_profiles(rules)
        return {
            "molécules": len(molecules),
            "éléments naturels": len(sources),
            "occurrences": Occurrence.objects.count(),
            "références": len(refs),
            "liens vin → molécule": n_links,
        }

    @staticmethod
    def _ref(refs: dict, key: str, ctx: str) -> Reference:
        try:
            return refs[key]
        except KeyError:
            raise KeyError(f"référence inconnue « {key} » ({ctx})") from None

    def _load_references(self) -> dict[str, Reference]:
        refs = {}
        for item in self._read("references.yaml"):
            key = item["key"]
            if key in refs:
                raise ValueError(f"référence en double : {key}")
            refs[key], _ = Reference.objects.update_or_create(
                key=key,
                defaults={
                    "authors": item["authors"],
                    "year": item.get("year"),
                    "title": item["title"],
                    "container": item.get("container", ""),
                    "doi": item.get("doi", ""),
                    "url": item.get("url", ""),
                    "note": item.get("note", ""),
                },
            )
        Reference.objects.exclude(key__in=refs).delete()
        return refs

    def _load_sources(self, aromas: dict) -> dict[str, NaturalSource]:
        out = {}
        for item in self._read("sources.yaml"):
            if item["kind"] not in NaturalSource.Kind.values:
                raise ValueError(f"{item['name']}: nature inconnue {item['kind']}")
            aroma = None
            if item.get("aroma"):
                aroma = aromas.get(normalize(item["aroma"]))
                if aroma is None:
                    raise KeyError(f"arôme inconnu « {item['aroma']} » (élément {item['name']})")
            src, _ = NaturalSource.objects.update_or_create(
                slug=slugify(item["name"]),
                defaults={
                    "name": item["name"],
                    "kind": item["kind"],
                    "latin_name": item.get("latin", ""),
                    "description": item.get("description", ""),
                    "aroma": aroma,
                },
            )
            out[normalize(item["name"])] = src
        NaturalSource.objects.exclude(pk__in=[s.pk for s in out.values()]).delete()
        return out

    def _link_profiles(self, rules) -> int:
        """Applique les règles à chaque profil et enregistre les liens justifiés."""
        ProfileMolecule.objects.all().delete()
        profiles = WineProfile.objects.prefetch_related("profile_grapes__grape", "profile_aromas__aroma")
        links = []
        for p in profiles:
            shares = {pg.grape_id: (pg.share, pg.grape.name) for pg in p.profile_grapes.all()}
            p_aromas = {pa.aroma_id: (pa.intensity, pa.aroma.name) for pa in p.profile_aromas.all()}
            for mol, parsed, mol_aromas, aroma_ref, aroma_max in rules:
                reasons = []
                for r in parsed:
                    if r.get("all"):
                        reasons.append({"basis": Basis.UNIVERSAL, "strength": r["strength"],
                                        "label": "Formée pendant la fermentation de tous les vins",
                                        "ref": r["ref"]})
                    for gid in r.get("grapes", []):
                        if gid in shares and shares[gid][0] >= r["min_share"]:
                            share, gname = shares[gid]
                            reasons.append({"basis": Basis.GRAPE, "strength": r["strength"],
                                            "label": f"{gname} ({share} % de l'encépagement)", "ref": r["ref"]})
                    if p.style in r.get("styles", []):
                        reasons.append({"basis": Basis.STYLE, "strength": r["strength"],
                                        "label": f"Style {p.get_style_display().lower()}", "ref": r["ref"]})
                    if p.color in r.get("colors", []):
                        reasons.append({"basis": Basis.COLOR, "strength": r["strength"],
                                        "label": f"Vin {p.get_color_display().lower()}", "ref": r["ref"]})
                for aid in mol_aromas & p_aromas.keys():
                    intensity, aname = p_aromas[aid]
                    strength = min(aroma_max, 2 if intensity == 3 else 1)
                    reasons.append({"basis": Basis.AROMA, "strength": strength,
                                    "label": f"Au nez : {aname} ({('discret', 'présent', 'dominant')[intensity - 1]})",
                                    "ref": aroma_ref})
                if not reasons:
                    continue
                reasons.sort(key=lambda x: (-x["strength"], BASIS_ORDER.index(x["basis"])))
                links.append(ProfileMolecule(
                    profile=p, molecule=mol, strength=reasons[0]["strength"],
                    basis=reasons[0]["basis"], reasons=[{**x, "basis": str(x["basis"])} for x in reasons],
                ))
        ProfileMolecule.objects.bulk_create(links)
        return len(links)
