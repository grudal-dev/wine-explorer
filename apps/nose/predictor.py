"""« Le Nez » : quels vins correspondent à ces arômes ?

Modèle bayésien naïf sur les profils types, avec repli par famille
aromatique : un descripteur absent d'un profil mais de la même famille qu'un
de ses arômes (framboise ↔ fraise) garde une vraisemblance non nulle.

    P(a | p) = (w_pa + α · w_pf(a) / n_f(a) + β) / (T_p · (1 + α) + β · N)

w_pa : intensité de l'arôme a dans le profil p (0-3)
w_pf : somme des intensités du profil p dans la famille de a
n_f  : nombre d'arômes de la famille
T_p  : somme des intensités du profil
N    : nombre total d'arômes

Les log-vraisemblances sont tempérées avant le softmax pour que les
probabilités affichées restent lisibles (un vrai sommelier hésite aussi).
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache

from apps.catalog.index import data_version
from apps.catalog.models import Aroma, AromaFamily, WineProfile

ALPHA = 0.6   # poids du repli par famille
BETA = 0.05   # lissage global
TEMPERATURE = 0.7


@dataclass
class _Model:
    profiles: list[dict]
    aroma_family: dict[int, int]
    family_size: dict[int, int]
    n_aromas: int
    aroma_names: dict[int, str]
    family_names: dict[int, str]


@lru_cache(maxsize=2)
def _model(version: tuple) -> _Model:
    aroma_family = dict(Aroma.objects.values_list("id", "family_id"))
    family_size: dict[int, int] = defaultdict(int)
    for fam in aroma_family.values():
        family_size[fam] += 1
    profiles = []
    qs = WineProfile.objects.select_related("appellation__region__parent").prefetch_related(
        "profile_aromas", "profile_grapes__grape"
    )
    for p in qs:
        weights = {pa.aroma_id: pa.intensity for pa in p.profile_aromas.all()}
        fam_w: dict[int, int] = defaultdict(int)
        for aid, w in weights.items():
            fam_w[aroma_family[aid]] += w
        reg = p.appellation.region
        profiles.append({
            "id": p.id,
            "name": p.name,
            "slug": p.slug,
            "url": p.get_absolute_url(),
            "color": p.color,
            "color_label": p.get_color_display(),
            "style": p.style,
            "style_label": p.get_style_display(),
            "region": (reg.parent or reg).name,
            "appellation": p.appellation.name,
            "grapes": [pg.grape.name for pg in p.profile_grapes.all()],
            "weights": weights,
            "family_weights": dict(fam_w),
            "total": sum(weights.values()) or 1,
        })
    return _Model(
        profiles=profiles,
        aroma_family=aroma_family,
        family_size=dict(family_size),
        n_aromas=len(aroma_family),
        aroma_names=dict(Aroma.objects.values_list("id", "name")),
        family_names=dict(AromaFamily.objects.values_list("id", "name")),
    )


def model() -> _Model:
    return _model(data_version())


def predict(aroma_ids: list[int], family_ids: list[int] | None = None, *,
            colors: list[str] | None = None, top: int = 5) -> dict:
    """Retourne le top `top` des profils avec probabilités et explications."""
    m = model()
    aroma_ids = [a for a in dict.fromkeys(aroma_ids) if a in m.aroma_family]
    family_ids = [f for f in dict.fromkeys(family_ids or []) if f in m.family_size]
    candidates = [p for p in m.profiles if not colors or p["color"] in colors]
    if not candidates or not (aroma_ids or family_ids):
        return {"results": [], "considered": len(candidates)}

    n_fam = len(m.family_size)
    scored = []
    for p in candidates:
        T = p["total"]
        z = T * (1 + ALPHA) + BETA * m.n_aromas
        ll = 0.0
        details = []
        for a in aroma_ids:
            fam = m.aroma_family[a]
            w = p["weights"].get(a, 0)
            fam_part = ALPHA * p["family_weights"].get(fam, 0) / m.family_size[fam]
            ll += math.log((w + fam_part + BETA) / z)
            details.append({
                "name": m.aroma_names[a],
                "match": "exact" if w else ("family" if p["family_weights"].get(fam) else "none"),
                "intensity": w,
            })
        for f in family_ids:
            ll += math.log((p["family_weights"].get(f, 0) + BETA) / (T + BETA * n_fam))
            details.append({
                "name": m.family_names[f],
                "match": "family" if p["family_weights"].get(f) else "none",
                "intensity": 0,
            })
        scored.append((ll, p, details))

    n_terms = len(aroma_ids) + len(family_ids)
    temp = TEMPERATURE * math.sqrt(n_terms)
    best = max(s[0] for s in scored)
    exps = [math.exp((s[0] - best) / temp) for s in scored]
    total = sum(exps)

    ranked = sorted(zip(exps, scored, strict=True), key=lambda t: -t[0])[:top]
    results = []
    for e, (_, p, details) in ranked:
        unmatched_profile = [
            m.aroma_names[a] for a, w in sorted(p["weights"].items(), key=lambda t: -t[1])
            if a not in aroma_ids and w >= 2
        ][:4]
        results.append({
            "probability": e / total,
            "profile": {k: p[k] for k in (
                "id", "name", "slug", "url", "color", "color_label", "style", "style_label",
                "region", "appellation", "grapes")},
            "matches": details,
            "exact": sum(1 for d in details if d["match"] == "exact"),
            "suggest": unmatched_profile,
        })
    return {"results": results, "considered": len(candidates)}


def reset():
    _model.cache_clear()
