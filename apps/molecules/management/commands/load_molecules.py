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
from django.utils.translation import gettext_noop

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
WIKIDATA_FILE = DATA_DIR / "wikidata_occurrences.json"

MOLECULE_KEYS = {
    "name", "name_en", "synonyms", "family", "origin", "smiles", "odor", "threshold", "refs",
    "aromas", "aroma_ref", "aroma_max", "universal", "description", "wine", "nature",
    "fades", "fault", "aroma_needs_rule",
}
CONDITION_KEYS = {"grapes", "styles", "colors", "oxidative", "all"}
RULE_KEYS = {"grapes", "styles", "colors", "oxidative", "all", "strength", "ref", "min_share"}


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

            from apps.explorer import graph as explorer_graph
            from apps.molecules import graph

            cache.clear()
            graph.reset()
            explorer_graph.reset()
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

        attack = {}
        for level, slugs in self._read("attack.yaml").items():
            if level not in (1, 2, 3):
                raise ValueError(f"attack.yaml : niveau inconnu {level}")
            for sl in slugs:
                if sl in attack:
                    raise ValueError(f"attack.yaml : {sl} classée deux fois")
                attack[sl] = level
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
                    "attack": attack.pop(slug, 2),
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
                if not set(rule) & CONDITION_KEYS:
                    raise ValueError(f"{name}: règle sans condition {rule}")
                if rule.get("all") and len(set(rule) & CONDITION_KEYS) > 1:
                    raise ValueError(f"{name}: « all » ne se combine avec aucune autre condition")
                self._ref(refs, rule["ref"], name)
                r = {"strength": strength, "ref": rule["ref"], "min_share": rule.get("min_share", MIN_SHARE)}
                if rule.get("all"):
                    r["all"] = True
                if rule.get("oxidative"):
                    r["oxidative"] = True
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
            fades = item.get("fades") or {}
            if set(fades) - {"oxidative", "ref"} or (fades and not fades.get("ref")):
                raise ValueError(f"{name}: règle « fades » invalide {fades}")
            if fades:
                self._ref(refs, fades["ref"], name)
            molecules.append(mol)
            if item.get("fault"):
                if parsed:
                    raise ValueError(f"{name}: une molécule de défaut ne porte pas de règle « wine »")
                continue   # décrite et reliée à la nature, jamais à un profil type
            rules.append({
                "fades_oxidative": bool(fades.get("oxidative")),
                "mol": mol, "parsed": parsed, "aromas": {a.pk for a in mol_aromas}, "aroma_ref": aroma_ref,
                "aroma_max": item.get("aroma_max", 2),
                "aroma_needs_rule": bool(item.get("aroma_needs_rule")),
            })
            if item.get("aroma_needs_rule") and not parsed:
                raise ValueError(f"{name}: « aroma_needs_rule » demande au moins une règle « wine »")

        if attack:
            raise ValueError(f"attack.yaml : molécules inconnues {sorted(attack)}")
        Molecule.objects.exclude(slug__in=seen_slugs).delete()
        n_imported = self._load_wikidata(refs, sources)
        n_links = self._link_profiles(rules)
        return {
            "molécules": len(molecules),
            "éléments naturels": len(sources),
            "occurrences": Occurrence.objects.filter(imported=False).count(),
            "occurrences importées de Wikidata": n_imported,
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
        NaturalSource.objects.filter(imported=False).exclude(pk__in=[s.pk for s in out.values()]).delete()
        return out

    def _load_wikidata(self, refs: dict, sources: dict) -> int:
        """Occurrences importées par import_wikidata_occurrences (fichier versionné, peut être vide)."""
        from apps.molecules.management.commands import load_molecules as module

        path = module.WIKIDATA_FILE
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        ref = refs.get("wikidata_lotus")
        by_latin = {s.latin_name.split(",")[0].strip().lower(): s for s in sources.values() if s.latin_name}
        kept_sources, n = set(), 0
        mols = {m.slug: m for m in Molecule.objects.all()}
        for slug, entry in data.items():
            mol = mols.get(slug)
            if mol is None:
                continue  # molécule retirée depuis l'import
            for t in entry.get("taxa", []):
                src = by_latin.get(t["latin"].lower())
                if src is None:
                    src, _ = NaturalSource.objects.update_or_create(
                        wikidata_id=t["qid"], imported=True,
                        defaults={"name": t["label"], "slug": f"wd-{t['qid'].lower()}",
                                  "kind": NaturalSource.Kind.ESPECE, "latin_name": t["latin"]},
                    )
                    kept_sources.add(src.pk)
                elif not src.wikidata_id:
                    src.wikidata_id = t["qid"]
                    src.save(update_fields=["wikidata_id"])
                # Une occurrence vérifiée à la main n'est jamais écrasée par l'import.
                _, created = Occurrence.objects.get_or_create(
                    molecule=mol, source=src,
                    defaults={"imported": True, "reference": ref, "note": f"Wikidata {entry.get('wikidata', '')}"},
                )
                n += created
        NaturalSource.objects.filter(imported=True).exclude(pk__in=kept_sources).delete()
        return n

    @staticmethod
    def _rule_reasons(r: dict, p, shares: dict) -> list[dict]:
        """Raisons qu'une règle donne à un profil : vide si l'une de ses conditions échoue (ET).

        La raison affichée est la plus précise : le cépage, sinon l'élevage ou le style, sinon la couleur.
        """
        if r.get("all"):
            return [{"basis": Basis.UNIVERSAL, "strength": r["strength"],
                     "label": gettext_noop("Formée pendant la fermentation de tous les vins"), "ref": r["ref"]}]
        if "colors" in r and p.color not in r["colors"]:
            return []
        if "styles" in r and p.style not in r["styles"]:
            return []
        if r.get("oxidative") and not p.oxidative:
            return []
        base = {"strength": r["strength"], "ref": r["ref"]}
        if "grapes" in r:
            return [{**base, "basis": Basis.GRAPE, "label": f"{shares[gid][1]} ({shares[gid][0]} % de l'encépagement)"}
                    for gid in r["grapes"] if gid in shares and shares[gid][0] >= r["min_share"]]
        if r.get("oxidative"):
            return [{**base, "basis": Basis.STYLE, "label": gettext_noop("Long élevage oxydatif")}]
        if "styles" in r:
            return [{**base, "basis": Basis.STYLE, "label": f"Style {p.get_style_display().lower()}"}]
        return [{**base, "basis": Basis.COLOR, "label": f"Vin {p.get_color_display().lower()}"}]

    def _link_profiles(self, rules) -> int:
        """Applique les règles à chaque profil et enregistre les liens justifiés.

        Deux sources seulement : les règles sourcées (cépage, style, couleur, socle commun) et les
        descripteurs du profil que la molécule explique. Plus de repli par famille d'arômes : il
        reliait l'eugénol à la « réglisse » ou le 3-sulfanylhexanol au « citron » d'un Chablis.
        """
        ProfileMolecule.objects.all().delete()
        profiles = WineProfile.objects.prefetch_related("profile_grapes__grape", "profile_aromas__aroma")
        links = []
        for p in profiles:
            shares = {pg.grape_id: (pg.share, pg.grape.name) for pg in p.profile_grapes.all()}
            p_aromas = {pa.aroma_id: (pa.intensity, pa.aroma.name) for pa in p.profile_aromas.all()}
            for rule in rules:
                # Molécule fragile disparue pendant un long élevage oxydatif (thiols, acétates) :
                # aucun lien, quelles que soient les autres raisons.
                if rule["fades_oxidative"] and p.oxidative:
                    continue
                reasons = [x for r in rule["parsed"] for x in self._rule_reasons(r, p, shares)]
                # Marqueur de cépage : le descripteur précise le lien (« rose » d'un Gewurztraminer) mais
                # n'en crée pas (la « rose » d'un Barolo ne vient pas de l'oxyde de rose).
                if rule["aroma_needs_rule"] and not reasons:
                    continue
                for aid in rule["aromas"] & p_aromas.keys():
                    intensity, aname = p_aromas[aid]
                    strength = min(rule["aroma_max"], 2 if intensity == 3 else 1)
                    reasons.append({"basis": Basis.AROMA, "strength": strength,
                                    "label": f"Au nez : {aname} ({('discret', 'présent', 'dominant')[intensity - 1]})",
                                    "ref": rule["aroma_ref"]})
                if not reasons:
                    continue
                reasons.sort(key=lambda x: (-x["strength"], BASIS_ORDER.index(x["basis"])))
                links.append(ProfileMolecule(
                    profile=p, molecule=rule["mol"], strength=reasons[0]["strength"],
                    basis=reasons[0]["basis"], reasons=[{**x, "basis": str(x["basis"])} for x in reasons],
                ))
        ProfileMolecule.objects.bulk_create(links)
        return len(links)
