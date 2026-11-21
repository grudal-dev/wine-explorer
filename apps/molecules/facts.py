"""« Le saviez-vous ? » : faits courts et sourcés sur les molécules du vin.

Lus une fois dans ``data/facts.yaml``. Chaque fait est rattaché à une molécule et à une référence
de la bibliographie ; le texte est donné en français et en anglais dans le fichier (pas de gettext).
"""

from __future__ import annotations

import random
from functools import lru_cache
from pathlib import Path

import yaml
from django.utils.translation import get_language

from apps.catalog.text import normalize

DATA = Path(__file__).resolve().parent / "data" / "facts.yaml"


@lru_cache(maxsize=1)
def _facts() -> tuple[dict, ...]:
    from .models import slug_for

    with DATA.open(encoding="utf-8") as fh:
        items = yaml.safe_load(fh) or []
    return tuple({**f, "slug": slug_for(f["molecule"]), "key": normalize(f["molecule"])} for f in items)


def _render(fact: dict) -> dict:
    from .models import Molecule, Reference

    english = (get_language() or "fr").startswith("en")
    mol = Molecule.objects.filter(slug=fact["slug"]).only("slug", "name").first()
    ref = Reference.objects.filter(key=fact["ref"]).first()
    return {
        "text": fact["text_en"] if english else fact["text"],
        "molecule": mol,
        "reference": ref,
    }


def for_molecule(slug: str) -> dict | None:
    """Le fait de cette molécule s'il existe, sinon un autre tiré au hasard."""
    facts = _facts()
    if not facts:
        return None
    own = [f for f in facts if f["slug"] == slug]
    return _render(own[0] if own else random.choice(facts))


def for_profile(profile, seed: str = "") -> dict | None:
    """Un fait sur une molécule de ce vin (lien propre, pas le socle commun), stable pour une partie
    (``seed``) ; à défaut, un fait au hasard, stable lui aussi."""
    from .models import Basis, ProfileMolecule

    facts = _facts()
    if not facts:
        return None
    slugs = {
        pm.molecule.slug
        for pm in ProfileMolecule.objects.filter(profile=profile).select_related("molecule")
        if not all(r["basis"] == Basis.UNIVERSAL for r in pm.reasons)
    }
    pool = [f for f in facts if f["slug"] in slugs] or list(facts)
    return _render(random.Random(seed or profile.pk).choice(pool))
