"""Appellations jumelles (data/jumelles.yaml) : indiscernables au verre, acceptées l'une pour l'autre au jeu."""

from functools import lru_cache
from pathlib import Path

import yaml
from django.utils.text import slugify

PATH = Path(__file__).resolve().parent / "data" / "jumelles.yaml"


@lru_cache(maxsize=1)
def groups() -> dict[str, frozenset[str]]:
    """slug → slugs de son groupe (lui compris)."""
    out: dict[str, frozenset[str]] = {}
    for names in yaml.safe_load(PATH.read_text(encoding="utf-8")) or []:
        group = frozenset(slugify(n) for n in names)
        for slug in group:
            if slug in out:
                raise ValueError(f"jumelles.yaml : {slug} est dans deux groupes")
            out[slug] = group
    return out


def are_twins(a_slug: str, b_slug: str) -> bool:
    return a_slug != b_slug and b_slug in groups().get(a_slug, ())
