"""Comparer deux vins : proximité apprise, bouche, nez en face-à-face, molécule signature.

Tout est calculé à la demande à partir de la base et de l'espace appris (`space()`) ; rien n'est
stocké. La proximité n'est pas un cosinus brut : c'est le rang de la paire parmi toutes les paires
de vins (« plus proches que 85 % des paires »), bien plus stable d'un entraînement à l'autre
(± 5 points sur cinq graines, contre ± 0,06 pour le cosinus).
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass, field
from functools import lru_cache

from django.utils.translation import gettext as _

from apps.catalog.i18n import tr
from apps.catalog.models import WineProfile

from .space import Space, space

# Paire proposée quand on arrive sur /comparer/ sans rien choisir.
DEFAULT_PAIR = ("barolo-rouge", "gevrey-chambertin-rouge")

# Duels mis en avant (plan du site, suggestions) : paires parlantes de la base.
FEATURED = [
    ("barolo-rouge", "gevrey-chambertin-rouge"),
    ("barolo-rouge", "barbaresco-rouge"),
    ("gevrey-chambertin-rouge", "chambolle-musigny-rouge"),
    ("sauternes-blanc", "tokaji-aszu"),
    ("barolo-rouge", "etna-rosso"),
    ("chablis-blanc", "meursault-blanc"),
]

NEIGHBOUR_MIN = 0.80   # deux arômes différents mais proches pour le modèle (truffe ≈ sous-bois)
NEIGHBOUR_MAX = 2      # au plus deux liens « arômes voisins », sinon le dessin se brouille


def band(percent: int) -> str:
    if percent >= 90:
        return _("Très proches")
    if percent >= 60:
        return _("Proches")
    if percent >= 25:
        return _("Éloignés")
    return _("Opposés")


@lru_cache(maxsize=4)
def _pair_scores(key: tuple) -> tuple[float, ...]:
    """Cosinus de toutes les paires de vins, triés : sert à situer une paire (centile)."""
    sp = space()
    wines = [i for i, t in enumerate(sp.types) if t == "profile"]
    vec = sp.vectors
    scores = []
    for n, i in enumerate(wines):
        vi = vec[i]
        for j in wines[n + 1:]:
            scores.append(sum(x * y for x, y in zip(vi, vec[j], strict=True)))
    scores.sort()
    return tuple(scores)


def proximity(sp: Space | None, a: WineProfile, b: WineProfile) -> int | None:
    """Centile de la paire (0 à 100) : part des paires de vins moins proches qu'elle."""
    if sp is None:
        return None
    sim = sp.similarity(f"profile:{a.slug}", f"profile:{b.slug}")
    if sim is None:
        return None
    scores = _pair_scores((sp.meta.get("trained"), len(sp.ids)))
    return round(100 * bisect_left(scores, sim) / len(scores)) if scores else None


@dataclass
class Aroma:
    slug: str
    name: str
    family: str
    family_color: str
    a: int = 0  # intensité dans le vin A (0 : absent)
    b: int = 0


@dataclass
class Nose:
    only_a: list[Aroma] = field(default_factory=list)
    common: list[Aroma] = field(default_factory=list)
    only_b: list[Aroma] = field(default_factory=list)
    neighbours: list[tuple[str, str]] = field(default_factory=list)  # (slug A, slug B)


def nose(sp: Space | None, a: WineProfile, b: WineProfile) -> Nose:
    found: dict[str, Aroma] = {}
    for side, wine in (("a", a), ("b", b)):
        for pa in wine.profile_aromas.select_related("aroma__family"):
            ar = pa.aroma
            item = found.setdefault(ar.slug, Aroma(ar.slug, tr(ar.name), tr(ar.family.name), ar.family.color))
            setattr(item, side, pa.intensity)
    key = lambda x: (-max(x.a, x.b), -(x.a + x.b), x.name)  # noqa: E731
    out = Nose(
        only_a=sorted((x for x in found.values() if x.a and not x.b), key=key),
        common=sorted((x for x in found.values() if x.a and x.b), key=key),
        only_b=sorted((x for x in found.values() if x.b and not x.a), key=key),
    )
    if sp is not None:
        pairs = []
        for x in out.only_a:
            for y in out.only_b:
                s = sp.similarity(f"aroma:{x.slug}", f"aroma:{y.slug}")
                if s is not None and s >= NEIGHBOUR_MIN:
                    pairs.append((s, x.slug, y.slug))
        used: set[str] = set()
        for _s, x, y in sorted(pairs, reverse=True):
            if x in used or y in used:
                continue
            out.neighbours.append((x, y))
            used |= {x, y}
            if len(out.neighbours) == NEIGHBOUR_MAX:
                break
    return out


def signature(wine: WineProfile, other: WineProfile) -> dict | None:
    """La molécule qui distingue le plus ce vin de l'autre : absente de l'autre, lien le plus fort."""
    theirs = set(other.profile_molecules.values_list("molecule_id", flat=True))
    links = (wine.profile_molecules.select_related("molecule")
             .exclude(molecule__universal=True).exclude(molecule_id__in=theirs)
             .order_by("-strength", "molecule__order", "molecule__name"))
    link = links.first()
    if link is None:
        return None
    m = link.molecule
    odor = ", ".join(part.strip() for part in tr(m.odor).split(",")[:2])
    return {"name": tr(m.name), "odor": odor, "url": m.get_absolute_url()}


def subtitle(wine: WineProfile) -> str:
    grapes = [tr(g.name) for g in wine.main_grapes()][:2]
    root = wine.appellation.region.root
    return " · ".join([", ".join(grapes), tr(root.name)] if grapes else [tr(root.name)])


def duel(a: WineProfile, b: WineProfile) -> dict:
    sp = space()
    percent = proximity(sp, a, b)
    mouth = []
    for (label, va), (_l, vb) in zip(a.structure, b.structure, strict=True):
        mouth.append({"label": label, "a": va, "b": vb, "delta": va - vb})
    return {
        "a": a, "b": b,
        "sub_a": subtitle(a), "sub_b": subtitle(b),
        "percent": percent,
        "band": band(percent) if percent is not None else "",
        "mouth": mouth,
        "nose": nose(sp, a, b),
        "sig_a": signature(a, b),
        "sig_b": signature(b, a),
    }
