"""Index de recherche en mémoire pour l'autocomplétion et la résolution des saisies.

Le volume (quelques centaines d'entités) tient largement en mémoire ; l'index
est reconstruit dès que la « version » des données change.
"""

from __future__ import annotations

from collections import defaultdict
from functools import lru_cache

from django.db.models import Count, Max

from .models import Appellation, Aroma, AromaFamily, Color, Grape, Region, Style, WineProfile
from .text import Match, best_matches, normalize

GUESS_KINDS = ("appellation", "region", "grape", "color", "style")
AROMA_KINDS = ("aroma",)

STYLE_ALIASES = {
    Style.EFFERVESCENT: ["bulles", "pétillant", "mousseux", "crémant"],
    Style.MOELLEUX: ["demi-sec", "doux"],
    Style.LIQUOREUX: ["botrytis", "pourriture noble"],
    Style.MUTE: ["VDN", "muté", "vin muté"],
    Style.OXYDATIF: ["vin jaune", "sous voile", "oxydatif"],
    Style.TRANQUILLE: ["sec", "tranquille"],
}
COLOR_ALIASES = {Color.ROSE: ["rose"], Color.ROUGE: [], Color.BLANC: []}


def data_version() -> tuple:
    agg = WineProfile.objects.aggregate(n=Count("id"), m=Max("id"))
    return (agg["n"], agg["m"], Aroma.objects.count(), Appellation.objects.count())


def _add(index, label, match):
    key = normalize(label)
    if key and match not in index[key]:
        index[key].append(match)


@lru_cache(maxsize=4)
def _build(version: tuple) -> dict[str, dict[str, list[Match]]]:
    guess: dict[str, list[Match]] = defaultdict(list)
    aroma: dict[str, list[Match]] = defaultdict(list)

    for a in Appellation.objects.only("id", "name"):
        _add(guess, a.name, Match("appellation", a.id, a.name, 1))
    for r in Region.objects.only("id", "name"):
        _add(guess, r.name, Match("region", r.id, r.name, 1))
    for g in Grape.objects.only("id", "name", "synonyms"):
        m = Match("grape", g.id, g.name, 1)
        for label in [g.name, *g.synonyms]:
            _add(guess, label, m)
    for value, label in Color.choices:
        m = Match("color", value, label, 1)
        for alias in [label, value, *COLOR_ALIASES.get(value, [])]:
            _add(guess, alias, m)
    for value, label in Style.choices:
        m = Match("style", value, label, 1)
        for alias in [label, *STYLE_ALIASES.get(value, [])]:
            _add(guess, alias, m)

    for ar in Aroma.objects.only("id", "name", "synonyms"):
        m = Match("aroma", ar.id, ar.name, 1)
        for label in [ar.name, *ar.synonyms]:
            _add(aroma, label, m)
    for fam in AromaFamily.objects.only("id", "name"):
        _add(aroma, fam.name, Match("family", fam.id, fam.name, 1))

    return {"guess": dict(guess), "aroma": dict(aroma)}


def guess_index():
    return _build(data_version())["guess"]


def aroma_index():
    return _build(data_version())["aroma"]


def search_guess(q: str, limit: int = 8) -> list[Match]:
    return best_matches(q, guess_index(), limit=limit)


def search_aroma(q: str, limit: int = 8, families: bool = False) -> list[Match]:
    res = best_matches(q, aroma_index(), limit=limit + 4)
    if not families:
        res = [m for m in res if m.kind == "aroma"]
    return res[:limit]


def reset():
    _build.cache_clear()
