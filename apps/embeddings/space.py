"""Espace de représentations apprises sur le graphe (voir la commande train_embeddings).

Chaque entité du graphe (vin, cépage, arôme, région, appellation, molécule, élément naturel)
porte un vecteur de quelques dizaines de dimensions, appris par un petit réseau de neurones
sur graphe. Deux entités proches dans cet espace se ressemblent par leurs voisinages : mêmes
arômes, mêmes cépages, même structure en bouche, même coin de France.

Le site ne fait que *lire* le fichier data/embeddings.json, versionné comme les formules des
molécules : ni PyTorch ni NumPy ne sont nécessaires pour le servir. Les vecteurs sont normés,
la similarité cosinus est donc un simple produit scalaire.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent / "data" / "embeddings.json"


@dataclass
class Space:
    ids: list[str]
    types: list[str]
    vectors: list[tuple[float, ...]]
    xy: list[tuple[float, float]]
    meta: dict
    index: dict[str, int] = field(default_factory=dict)
    _rank_cache: dict[str, dict[str, int]] = field(default_factory=dict)

    def __post_init__(self):
        self.index = {node_id: i for i, node_id in enumerate(self.ids)}

    def __contains__(self, node_id: str) -> bool:
        return node_id in self.index

    def similarity(self, a: str, b: str) -> float | None:
        """Cosinus entre deux entités, de -1 à 1 ; None si l'une d'elles n'a pas de vecteur."""
        i, j = self.index.get(a), self.index.get(b)
        if i is None or j is None:
            return None
        return sum(x * y for x, y in zip(self.vectors[i], self.vectors[j], strict=True))

    def neighbours(self, node_id: str, *, types: tuple[str, ...] | None = None, k: int = 8,
                   exclude: tuple[str, ...] = ()) -> list[tuple[str, float]]:
        """Les k entités les plus proches, éventuellement restreintes à certains types."""
        i = self.index.get(node_id)
        if i is None:
            return []
        v = self.vectors[i]
        scored = []
        for j, other in enumerate(self.ids):
            if j == i or other in exclude or (types and self.types[j] not in types):
                continue
            scored.append((sum(x * y for x, y in zip(v, self.vectors[j], strict=True)), other))
        scored.sort(reverse=True)
        return [(other, s) for s, other in scored[:k]]

    def ranks(self, node_id: str) -> dict[str, int]:
        """Rang de proximité de chaque entité par rapport à `node_id` (1 = la plus proche)."""
        if node_id not in self._rank_cache:
            if len(self._rank_cache) > 64:
                self._rank_cache.clear()
            ordered = self.neighbours(node_id, k=len(self.ids))
            self._rank_cache[node_id] = {other: rank for rank, (other, _s) in enumerate(ordered, start=1)}
        return self._rank_cache[node_id]

    def position(self, node_id: str) -> tuple[float, float] | None:
        i = self.index.get(node_id)
        return self.xy[i] if i is not None else None


@lru_cache(maxsize=2)
def _load(mtime: float) -> Space | None:
    try:
        raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return Space(
        ids=raw["ids"], types=raw["types"],
        vectors=[tuple(v) for v in raw["vectors"]],
        xy=[tuple(p) for p in raw["xy"]],
        meta=raw.get("meta", {}),
    )


def space() -> Space | None:
    """L'espace appris, ou None tant que train_embeddings n'a pas été lancé."""
    try:
        return _load(DATA_FILE.stat().st_mtime)
    except OSError:
        return None
