"""« Le Nez » : quels vins correspondent à ces arômes ?

Modèle bayésien naïf sur les profils types. Un descripteur absent d'un profil n'est pas
éliminatoire : il garde une vraisemblance partielle s'il est *proche* d'un arôme du profil.

    P(a | p) = (w_pa + α · s_pa + β) / (T_p · (1 + α) + β · N)

w_pa : intensité de l'arôme a dans le profil p (0-3)
s_pa : repli pour un arôme absent, selon ce qui est disponible :
       - proximité apprise (défaut) : max sur les arômes b du profil de (w_pb / 3) · k(a, b)^γ,
         où k est la similarité entre a et b dans l'espace appris sur le graphe
         (apps/embeddings), recentrée entre 0 et 1. Le repli reste donc entre 0 et 1.
         La framboise profite ainsi d'une fraise, mais aussi d'une violette qu'elle côtoie
         souvent, ce qu'une famille ne sait pas dire ;
       - famille aromatique (si les vecteurs manquent) : part des arômes de la même famille.
T_p  : somme des intensités du profil
N    : nombre total d'arômes

Ce que disent les mesures (train_embeddings, arômes masqués, environ 500 cas sur six
découpages ; rang réciproque moyen du bon vin, 1 = toujours premier) :
    proximité apprise (α = 1,5, γ = 0,5)   0,58 à 0,61 selon le découpage
    aucun repli                             0,58
    ancien repli par famille (α = 0,6)      0,45 à 0,49
Le vrai gain est d'avoir quitté le repli par famille, qui dégradait le classement. La proximité
apprise fait jeu égal avec « aucun repli », parfois un peu mieux, et elle a un avantage que
l'absence de repli n'a pas : elle explique (« ≈ fraise ») pourquoi un vin reste plausible. Le
repli par famille n'est gardé, avec un poids faible, que si les vecteurs manquent.

Les descripteurs sensoriels (bouche, style, voir sensory.py) ajoutent un terme
gaussien par axe : exp(-(valeur du profil - cible)² / 2σ²), avec un plancher.

Les log-vraisemblances sont tempérées avant le softmax pour que les
probabilités affichées restent lisibles (un vrai sommelier hésite aussi).
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache

from apps.catalog.i18n import tr
from apps.catalog.index import data_version
from apps.catalog.models import Aroma, AromaFamily, Color, Style, WineProfile

from . import sensory

ALPHA = 1.5          # poids du repli par proximité apprise
ALPHA_FAMILY = 0.3   # poids du repli par famille, quand les vecteurs manquent
GAMMA = 0.5          # exposant de la proximité apprise (au-delà de 1, les mesures se dégradent)
LENGTH_POWER = 1.0   # 1 : normalisation bayésienne par la richesse du profil ; 0 : aucune
CLOSE_THRESHOLD = 0.4  # en dessous, on n'affiche pas « proche »
_UNSET = object()
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
    aroma_slugs: dict[int, str]
    kernel: object = _UNSET  # proximité apprise entre arômes, calculée à la première demande


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
            "color_label": Color(p.color).label,  # paresseux : traduit à l'affichage
            "style": p.style,
            "style_label": Style(p.style).label,
            "region": (reg.parent or reg).name,
            "appellation": p.appellation.name,
            "grapes": [pg.grape.name for pg in p.profile_grapes.all()],
            "weights": weights,
            "family_weights": dict(fam_w),
            "structure": {"body": p.body, "acidity": p.acidity, "tannin": p.tannin, "sweetness": p.sweetness},
            "total": sum(weights.values()) or 1,
        })
    return _Model(
        profiles=profiles,
        aroma_family=aroma_family,
        family_size=dict(family_size),
        n_aromas=len(aroma_family),
        aroma_names=dict(Aroma.objects.values_list("id", "name")),
        family_names=dict(AromaFamily.objects.values_list("id", "name")),
        aroma_slugs=dict(Aroma.objects.values_list("id", "slug")),
    )


def model() -> _Model:
    return _model(data_version())


def _sense_term(p: dict, t: sensory.Term) -> tuple[float, dict]:
    """Log-vraisemblance d'un descripteur sensoriel pour un profil, et son explication."""
    if t.axis == "style":
        ok = p["style"] == t.style
        prob = sensory.STYLE_MATCH if ok else sensory.STYLE_MISS
        return math.log(prob), {"name": tr(t.label), "match": "exact" if ok else "none", "intensity": 0,
                                "sense": True, "actual": str(p["style_label"])}
    value = p["structure"][t.axis]
    d = value - t.target
    prob = math.exp(-(d * d) / (2 * sensory.SIGMA ** 2)) * (1 - sensory.FLOOR) + sensory.FLOOR
    match = "exact" if abs(d) <= 0.75 else ("family" if abs(d) <= 1.5 else "none")
    return math.log(prob), {"name": tr(t.label), "match": match, "intensity": 0, "sense": True,
                            "actual": f"{str(sensory.AXES[t.axis]).lower()} {value}/5"}


def make_kernel(m: _Model, similarity):
    """Proximité apprise entre deux arômes (0 à 1) à partir de `similarity(slug_a, slug_b)`.

    Les cosinus bruts entre arômes sont tous assez élevés (ce sont tous des arômes) : on les
    recentre sur la moyenne de chaque arôme, pour que 0 signifie « ni plus ni moins proche qu'un
    arôme quelconque » et 1 « identique ». Rend None s'il n'y a pas assez de vecteurs.
    """
    ids = [a for a, slug in m.aroma_slugs.items() if similarity(slug, slug) is not None]
    if len(ids) < 2:
        return None
    table: dict[tuple[int, int], float] = {}
    for a in ids:
        sims = {b: similarity(m.aroma_slugs[a], m.aroma_slugs[b]) for b in ids if b != a}
        mean = sum(sims.values()) / len(sims)
        for b, s in sims.items():
            table[(a, b)] = max(0.0, (s - mean) / (1 - mean)) if mean < 1 else 0.0

    def kernel(a: int, b: int) -> float:
        # Symétrisé : la proximité de a à b et celle de b à a ne sont pas recentrées pareil.
        return (table.get((a, b), 0.0) + table.get((b, a), 0.0)) / 2

    kernel.known = frozenset(ids)  # les arômes qu'aucun vin ne cite n'ont pas de vecteur
    return kernel


def _kernel_from_space(m: _Model):
    from apps.embeddings.space import space

    sp = space()
    if sp is None:
        return None
    return make_kernel(m, lambda a, b: sp.similarity(f"aroma:{a}", f"aroma:{b}"))


def default_fallback(m: _Model):
    """Le repli utilisé par le site : proximité apprise si elle existe, sinon famille aromatique."""
    if m.kernel is _UNSET:
        m.kernel = _kernel_from_space(m)
    return m.kernel or "family"


def _aroma_term(m: _Model, p: dict, a: int, fallback) -> tuple[float, dict]:
    """Vraisemblance d'un arôme pour un profil, et de quoi l'expliquer.

    `fallback` décide ce que vaut un arôme absent du profil :
      - une fonction k(a, b) entre 0 et 1 : proximité apprise avec les arômes du profil ;
      - "family" : part des arômes de la même famille (comportement historique) ;
      - None : rien.
    """
    w = p["weights"].get(a, 0)
    fam = m.aroma_family[a]
    soft, near = 0.0, None
    weight = _alpha(fallback)
    if callable(fallback) and a not in getattr(fallback, "known", (a,)):
        fallback = "family"  # arôme sans vecteur : il ne lui reste que sa famille
    if callable(fallback):
        for b, wb in p["weights"].items():
            if b == a:
                continue
            s = (wb / 3) * fallback(a, b) ** GAMMA  # entre 0 et 1 : un arôme proche ne vaut jamais un arôme présent
            if s > soft:
                soft, near = s, b
        close = soft >= CLOSE_THRESHOLD
    elif fallback == "family":
        soft = p["family_weights"].get(fam, 0) / m.family_size[fam]
        close = bool(p["family_weights"].get(fam))
    else:
        close = False
    detail = {"match": "exact" if w else ("family" if close else "none"), "intensity": w, "aroma": a}
    if not w and close and near is not None:
        detail["near"] = near
    return w + weight * soft + BETA, detail


def _alpha(fallback) -> float:
    return ALPHA if callable(fallback) else (ALPHA_FAMILY if fallback == "family" else 0.0)


def _normaliser(m: _Model, p: dict, fallback) -> float:
    return p["total"] ** LENGTH_POWER * (1 + _alpha(fallback)) + BETA * m.n_aromas


def rank(m: _Model, aroma_ids: list[int], *, fallback="family") -> list[dict]:
    """Profils classés du plus au moins vraisemblable pour ces arômes (sert à l'évaluation)."""
    scored = []
    for p in m.profiles:
        z = _normaliser(m, p, fallback)
        ll = sum(math.log(_aroma_term(m, p, a, fallback)[0] / z) for a in aroma_ids)
        scored.append((ll, p["slug"], p))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [p for _ll, _slug, p in scored]


def predict(aroma_ids: list[int], family_ids: list[int] | None = None, *,
            colors: list[str] | None = None, senses: list[str] | None = None, top: int = 5) -> dict:
    """Retourne le top `top` des profils avec probabilités et explications."""
    m = model()
    aroma_ids = [a for a in dict.fromkeys(aroma_ids) if a in m.aroma_family]
    family_ids = [f for f in dict.fromkeys(family_ids or []) if f in m.family_size]
    terms = sensory.clean(senses or [])
    candidates = [p for p in m.profiles if not colors or p["color"] in colors]
    if not candidates or not (aroma_ids or family_ids or terms):
        return {"results": [], "considered": len(candidates)}

    fallback = default_fallback(m)
    n_fam = len(m.family_size)
    scored = []
    for p in candidates:
        T = p["total"]
        z = _normaliser(m, p, fallback)
        ll = 0.0
        details = []
        for a in aroma_ids:
            value, detail = _aroma_term(m, p, a, fallback)
            ll += math.log(value / z)
            detail["name"] = tr(m.aroma_names[a])
            if "near" in detail:
                detail["near"] = tr(m.aroma_names[detail["near"]])
            details.append(detail)
        for f in family_ids:
            ll += math.log((p["family_weights"].get(f, 0) + BETA) / (T + BETA * n_fam))
            details.append({
                "name": tr(m.family_names[f]),
                "match": "family" if p["family_weights"].get(f) else "none",
                "intensity": 0,
            })
        for t in terms:
            term_ll, detail = _sense_term(p, t)
            ll += term_ll
            details.append(detail)
        scored.append((ll, p, details))

    n_terms = len(aroma_ids) + len(family_ids) + len(terms)
    temp = TEMPERATURE * math.sqrt(n_terms)
    best = max(s[0] for s in scored)
    exps = [math.exp((s[0] - best) / temp) for s in scored]
    total = sum(exps)

    ranked = sorted(zip(exps, scored, strict=True), key=lambda t: -t[0])[:top]
    results = []
    for e, (_, p, details) in ranked:
        unmatched_profile = [
            tr(m.aroma_names[a]) for a, w in sorted(p["weights"].items(), key=lambda t: -t[1])
            if a not in aroma_ids and w >= 2
        ][:4]
        results.append({
            "probability": e / total,
            "profile": {k: p[k] for k in (
                "id", "name", "slug", "url", "color", "color_label", "style", "style_label",
                "region", "appellation", "grapes")} | {"region": tr(p["region"])},
            "matches": details,
            "exact": sum(1 for d in details if d["match"] == "exact"),
            "structure": p["structure"],
            "suggest": unmatched_profile,
        })
    return {"results": results, "considered": len(candidates)}


def reset():
    _model.cache_clear()
