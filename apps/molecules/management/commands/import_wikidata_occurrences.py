"""Importe depuis Wikidata les espèces où chaque molécule a été trouvée (propriété P703).

    python manage.py import_wikidata_occurrences            # interroge Wikidata, écrit le fichier
    python manage.py import_wikidata_occurrences --dry-run  # affiche sans écrire
    python manage.py load_molecules                         # charge les occurrences importées

Les données P703 viennent en grande partie de l'initiative LOTUS (produits naturels
publiés) et sont sous licence CC0. Elles ne sont pas vérifiées une à une : elles sont
écrites dans data/wikidata_occurrences.json, chargées avec le drapeau « importé » et
affichées à part dans l'interface.

Pour rester lisible, on ne garde que les taxons qui ont un article sur Wikipédia en
français (un bon indicateur d'espèce connue) et un nom français, au plus --limit par
molécule. La molécule est retrouvée par son InChIKey (calculée par render_molecules),
puis, à défaut, par son nom anglais.
"""

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.molecules.models import Molecule

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
OUTPUT = DATA_DIR / "wikidata_occurrences.json"
ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "Terroirs/1.0 (https://github.com/grudal-dev/wine-explorer; explorateur pedagogique du vin)"

QUERY = """
SELECT DISTINCT ?mol ?taxon ?latin ?labelFr WHERE {{
  {{ ?mol wdt:P235 "{inchikey}" . }}
  UNION
  {{ ?mol rdfs:label "{name_en}"@en ; wdt:P31/wdt:P279* wd:Q11173 . }}
  ?mol wdt:P703 ?taxon .
  ?taxon wdt:P225 ?latin ;
         rdfs:label ?labelFr .
  FILTER(LANG(?labelFr) = "fr")
  ?article schema:about ?taxon ;
           schema:isPartOf <https://fr.wikipedia.org/> .
}}
LIMIT 200
"""


def sparql(query: str, timeout: int = 60) -> dict:
    url = f"{ENDPOINT}?{urllib.parse.urlencode({'query': query, 'format': 'json'})}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - URL fixe
        return json.load(resp)


def qid(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def parse(bindings: list[dict], limit: int) -> tuple[str, list[dict]]:
    """Regroupe les taxons, garde le premier item molécule rencontré et au plus ``limit`` taxons."""
    mol_qid = ""
    taxa: dict[str, dict] = {}
    for b in bindings:
        mol_qid = mol_qid or qid(b["mol"]["value"])
        t = qid(b["taxon"]["value"])
        if t in taxa:
            continue
        label = b["labelFr"]["value"]
        latin = b["latin"]["value"]
        if label.strip().lower() == latin.strip().lower():
            label = latin  # pas de nom vernaculaire : on garde le nom scientifique
        taxa[t] = {"qid": t, "label": label, "latin": latin}
    # Les espèces au nom vernaculaire d'abord : plus parlantes pour le public.
    ordered = sorted(taxa.values(), key=lambda x: (x["label"] == x["latin"], x["label"].lower()))
    return mol_qid, ordered[:limit]


class Command(BaseCommand):
    help = "Interroge Wikidata (P703) et écrit data/wikidata_occurrences.json."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=6, help="Taxons gardés par molécule (défaut 6).")
        parser.add_argument("--dry-run", action="store_true", help="Afficher sans écrire le fichier.")
        parser.add_argument("--pause", type=float, default=1.0, help="Pause entre requêtes, en secondes.")

    def handle(self, *args, limit, dry_run, pause, **options):
        computed = json.loads((DATA_DIR / "computed.json").read_text(encoding="utf-8"))
        result, errors = {}, []
        for mol in Molecule.objects.order_by("order"):
            inchikey = computed.get(mol.slug, {}).get("inchikey", "")
            query = QUERY.format(inchikey=inchikey.replace('"', ""), name_en=mol.name_en.replace('"', ""))
            try:
                data = sparql(query)
            except OSError as exc:
                errors.append(f"{mol.name} : {exc}")
                continue
            mol_qid, taxa = parse(data["results"]["bindings"], limit)
            if taxa:
                result[mol.slug] = {"wikidata": mol_qid, "taxa": taxa}
            self.stdout.write(f"  {mol.name:<32} {mol_qid or '—':<12} {len(taxa)} taxon(s)")
            time.sleep(pause)
        if errors and not result:
            raise CommandError("Wikidata injoignable :\n  " + "\n  ".join(errors))
        for e in errors:
            self.stderr.write(f"  ignoré : {e}")
        if dry_run:
            self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
            return
        OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        n = sum(len(v["taxa"]) for v in result.values())
        self.stdout.write(self.style.SUCCESS(
            f"{n} occurrences pour {len(result)} molécules écrites dans {OUTPUT.name}. Lancez load_molecules."
        ))
