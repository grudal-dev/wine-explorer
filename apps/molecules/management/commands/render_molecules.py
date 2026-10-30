"""Dessine les formules développées et calcule formule brute et masse molaire.

    pip install rdkit
    python manage.py render_molecules

Commande de développement : elle lit les SMILES de data/molecules.yaml, écrit
une image SVG par molécule dans static/molecules/ et les propriétés calculées
dans data/computed.json. Les deux sont versionnés, si bien que RDKit n'est pas
nécessaire pour faire tourner le site.
"""

import json
from pathlib import Path

import yaml
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.molecules.models import slug_for

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# Encre et teintes de la charte (voir static/css/app.css).
INK = (0x23 / 255, 0x26 / 255, 0x2F / 255)
HETERO = {
    8: (0x7A / 255, 0x1F / 255, 0x3D / 255),   # O : grenat
    16: (0xB0 / 255, 0x7D / 255, 0x22 / 255),  # S : ocre
    7: (0x3B / 255, 0x58 / 255, 0x78 / 255),   # N : ardoise
}


class Command(BaseCommand):
    help = "Génère les SVG des molécules et data/computed.json (nécessite RDKit)."

    def handle(self, *args, **options):
        try:
            from rdkit import Chem
            from rdkit.Chem import Descriptors, rdDepictor, rdMolDescriptors
            from rdkit.Chem.Draw import rdMolDraw2D
        except ImportError as exc:  # pragma: no cover - dépend de l'environnement
            raise CommandError("RDKit est requis : pip install rdkit") from exc

        out_dir = Path(settings.BASE_DIR) / "static" / "molecules"
        out_dir.mkdir(parents=True, exist_ok=True)
        rdDepictor.SetPreferCoordGen(True)

        with (DATA_DIR / "molecules.yaml").open(encoding="utf-8") as fh:
            items = yaml.safe_load(fh)

        computed = {}
        for item in items:
            slug = slug_for(item["name"])
            mol = Chem.MolFromSmiles(item["smiles"])
            if mol is None:
                raise CommandError(f"SMILES invalide pour {item['name']}: {item['smiles']}")
            computed[slug] = {
                "formula": rdMolDescriptors.CalcMolFormula(mol),
                "molar_mass": round(Descriptors.MolWt(mol), 2),
                "inchikey": Chem.MolToInchiKey(mol),
            }
            rdDepictor.Compute2DCoords(mol)
            drawer = rdMolDraw2D.MolDraw2DSVG(320, 220)
            opts = drawer.drawOptions()
            opts.clearBackground = False
            opts.bondLineWidth = 2
            opts.padding = 0.12
            opts.fixedBondLength = 34
            opts.minFontSize = 15
            opts.setAtomPalette({0: INK, 6: INK, 1: INK, **HETERO})
            drawer.DrawMolecule(mol)
            drawer.FinishDrawing()
            svg = drawer.GetDrawingText()
            svg = svg.replace("<?xml version='1.0' encoding='iso-8859-1'?>\n", "")
            svg = svg.replace("<svg ", f"<svg role=\"img\" aria-label=\"Formule de {item['name']}\" ", 1)
            (out_dir / f"{slug}.svg").write_text(svg, encoding="utf-8")
            self.stdout.write(f"  {item['name']:<32} {computed[slug]['formula']:<12} {computed[slug]['molar_mass']}")

        (DATA_DIR / "computed.json").write_text(
            json.dumps(computed, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        self.stdout.write(self.style.SUCCESS(f"{len(computed)} molécules dessinées dans {out_dir}"))
