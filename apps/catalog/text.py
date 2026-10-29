"""Normalisation de texte et résolution de saisies libres vers des entités."""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass

_SPACES = re.compile(r"[\s\-'’_]+")


def normalize(text: str) -> str:
    """Minuscule, sans accents, ponctuation légère unifiée : « Côte-Rôtie » → « cote rotie »."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("œ", "oe").replace("æ", "ae")
    return _SPACES.sub(" ", text.lower()).strip()


@dataclass(frozen=True)
class Match:
    kind: str  # appellation | region | grape | aroma | color | style
    pk: int | str
    label: str
    score: float


def best_matches(query: str, index: dict[str, list[Match]], limit: int = 8,
                 cutoff: float = 0.72) -> list[Match]:
    """Recherche dans un index {libellé normalisé: [Match]} : exact, préfixe, puis flou."""
    q = normalize(query)
    if not q:
        return []
    results: dict[tuple[str, object], Match] = {}

    def add(matches: list[Match], score: float):
        for m in matches:
            key = (m.kind, m.pk)
            if key not in results or results[key].score < score:
                results[key] = Match(m.kind, m.pk, m.label, score)

    if q in index:
        add(index[q], 1.0)
    for label, matches in index.items():
        if label.startswith(q) and label != q:
            add(matches, 0.9 - min(len(label) - len(q), 20) / 100)
        elif len(q) >= 3 and f" {q}" in f" {label}":
            add(matches, 0.75)
    if len(results) < limit:
        for label in difflib.get_close_matches(q, list(index), n=limit, cutoff=cutoff):
            ratio = difflib.SequenceMatcher(None, q, label).ratio()
            add(index[label], 0.6 * ratio)
    return sorted(results.values(), key=lambda m: (-m.score, m.label))[:limit]
