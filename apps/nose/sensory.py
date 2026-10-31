"""Vocabulaire sensoriel du Nez : la bouche (corps, acidité, tanins, sucrosité) et le style.

Chaque terme vise une valeur sur l'échelle 0-5 des profils types (WineProfile.body,
acidity, tannin, sweetness) ou un style. Le prédicteur compare cette cible à la
valeur du profil avec une vraisemblance gaussienne : un vin « vif » n'exclut pas
un profil d'acidité 3, il le rend seulement moins probable qu'un profil à 5.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from apps.catalog.text import normalize

AXES = {
    "body": "Corps",
    "acidity": "Acidité",
    "tannin": "Tanins",
    "sweetness": "Sucrosité",
    "style": "Style",
}


@dataclass(frozen=True)
class Term:
    key: str
    label: str
    axis: str
    target: float | None = None   # axes chiffrés
    style: str = ""               # axe « style »
    synonyms: tuple[str, ...] = field(default_factory=tuple)


TERMS: tuple[Term, ...] = (
    Term("leger", "léger", "body", 1.5, synonyms=("fluide", "gouleyant", "aérien", "peu de corps")),
    Term("ample", "ample", "body", 3.5, synonyms=("rond", "charnu", "gras", "corps moyen")),
    Term("puissant", "puissant", "body", 5, synonyms=("charpenté", "corsé", "massif", "capiteux")),
    Term("acidite-douce", "acidité douce", "acidity", 2, synonyms=("peu acide", "souple", "plat", "mou")),
    Term("frais", "frais", "acidity", 3.5, synonyms=("fraîcheur", "équilibré")),
    Term("vif", "vif", "acidity", 5, synonyms=("nerveux", "tendu", "acide", "tranchant", "ciselé")),
    Term("sans-tanins", "sans tanins", "tannin", 0, synonyms=("pas de tanins",)),
    Term("tanins-soyeux", "tanins soyeux", "tannin", 2, synonyms=("soyeux", "velouté", "tanins fondus", "fondu")),
    Term("tannique", "tannique", "tannin", 4, synonyms=("ferme", "tanins présents", "structuré")),
    Term("astringent", "astringent", "tannin", 5, synonyms=("austère", "asséchant", "rugueux", "très tannique")),
    Term("sec", "sec", "sweetness", 1, synonyms=("pas sucré", "brut")),
    Term("demi-sec", "demi-sec", "sweetness", 2.5, synonyms=("tendre", "légèrement sucré")),
    Term("moelleux", "moelleux", "sweetness", 3.5, synonyms=("doux", "sucré")),
    Term("liquoreux", "liquoreux", "sweetness", 5, synonyms=("sirupeux", "très sucré", "botrytisé")),
    Term("bulles", "bulles", "style", style="effervescent",
         synonyms=("effervescent", "pétillant", "mousseux", "crémant", "perlant")),
    Term("sous-voile", "sous voile", "style", style="oxydatif", synonyms=("oxydatif", "vin jaune", "voile")),
    Term("mute", "muté", "style", style="mute", synonyms=("vin doux naturel", "vdn", "fortifié", "rancio")),
)
BY_KEY = {t.key: t for t in TERMS}

SIGMA = 0.9         # tolérance d'un cran environ
FLOOR = 0.02        # un terme ne rend jamais un profil impossible
STYLE_MATCH, STYLE_MISS = 0.85, 0.02


def search(q: str, limit: int = 4) -> list[Term]:
    """Termes dont le libellé ou un synonyme commence par (puis contient) la saisie."""
    nq = normalize(q)
    if not nq:
        return []
    scored = []
    for t in TERMS:
        labels = [normalize(t.label), *(normalize(s) for s in t.synonyms)]
        if any(lab == nq for lab in labels):
            rank = 0
        elif any(lab.startswith(nq) for lab in labels):
            rank = 1
        elif any(nq in lab for lab in labels):
            rank = 2
        else:
            continue
        scored.append((rank, t.label, t))
    return [t for _, _, t in sorted(scored)[:limit]]


def exact(q: str) -> Term | None:
    """Terme dont le libellé ou un synonyme est exactement la saisie (accents et casse ignorés)."""
    nq = normalize(q)
    for t in TERMS:
        if nq and nq in {normalize(t.label), *(normalize(x) for x in t.synonyms)}:
            return t
    return None


def grouped() -> list[tuple[str, str, list[Term]]]:
    """Pour l'interface : [(axe, libellé, termes)]."""
    return [(axis, label, [t for t in TERMS if t.axis == axis]) for axis, label in AXES.items()]


def clean(keys) -> list[Term]:
    """Termes valides, un seul par axe (le dernier choisi l'emporte)."""
    by_axis: dict[str, Term] = {}
    for k in keys:
        t = BY_KEY.get(k)
        if t:
            by_axis[t.axis] = t
    return list(by_axis.values())
