"""Familles de vins sur la carte des goûts : regroupement des points voisins et nom de chaque groupe.

Sur téléphone, la carte arrive en vue d'ensemble : une étiquette par groupe (« Liquoreux », « Rouges ·
Bourgogne »…) à la place de 138 noms illisibles ; toucher une étiquette zoome sur ses vins. Les groupes
sont calculés à la volée (k-moyennes sur les positions 2D de la carte, sans NumPy), donc suivent
chaque réentraînement.
"""

from __future__ import annotations

from collections import Counter
from functools import lru_cache

from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop as N_

from apps.catalog.i18n import tr

K = 9           # nombre de groupes : lisible sur un écran de téléphone
MAJORITY = 0.6  # part à atteindre pour nommer un groupe par son style ou sa couleur


def _kmeans(points: list[tuple[float, float]], k: int, rounds: int = 30) -> list[int]:
    k = min(k, len(points))
    # Départ déterministe : le point le plus à gauche, puis à chaque fois le plus éloigné des centres.
    centres = [min(points)]
    while len(centres) < k:
        centres.append(max(points, key=lambda p: min((p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2 for c in centres)))
    labels = [0] * len(points)
    for _round in range(rounds):
        labels = [min(range(k), key=lambda i: (p[0] - centres[i][0]) ** 2 + (p[1] - centres[i][1]) ** 2) for p in points]
        moved = False
        for i in range(k):
            members = [p for p, lab in zip(points, labels, strict=True) if lab == i]
            if not members:
                continue
            c = (sum(p[0] for p in members) / len(members), sum(p[1] for p in members) / len(members))
            moved |= c != centres[i]
            centres[i] = c
        if not moved:
            break
    return labels


STYLE_NAMES = {
    "effervescent": N_("Bulles"),
    "liquoreux": N_("Liquoreux et moelleux"),
    "moelleux": N_("Liquoreux et moelleux"),
    "mute": N_("Vins doux naturels"),
    "oxydatif": N_("Vins jaunes"),
}
COLOR_NAMES = {"rouge": N_("Rouges"), "blanc": N_("Blancs"), "rose": N_("Rosés")}
# Noms de région raccourcis pour tenir dans une étiquette de téléphone.
SHORT = {"Vallée du Rhône": "Rhône", "Vallée de la Loire": "Loire", "Languedoc-Roussillon": "Languedoc"}


def _region(name: str) -> str:
    return SHORT[name] if name in SHORT else tr(name)


def name(wines: list[dict]) -> str:
    n = len(wines)
    styles = Counter(STYLE_NAMES.get(w["style"]) for w in wines if w["style"] in STYLE_NAMES)
    if styles:
        label, count = styles.most_common(1)[0]
        if count / n >= MAJORITY:
            return _(label)
    colour, count = Counter(w["color"] for w in wines).most_common(1)[0]
    head = _(COLOR_NAMES[colour]) if colour in COLOR_NAMES and count / n >= MAJORITY else _("Vins")
    roots = Counter(w["root"] for w in wines).most_common(2)
    if roots[0][1] / n >= 0.5 or len(roots) == 1:
        return f"{head} · {_region(roots[0][0])}"
    return f"{head} · {_region(roots[0][0])}, {_region(roots[1][0])}"


@lru_cache(maxsize=4)
def _groups(key: tuple, lang: str) -> tuple[dict[str, int], tuple[dict, ...]]:
    from apps.catalog.models import WineProfile

    from .space import space

    sp = space()
    info = {w.slug: {"style": w.style, "color": w.color, "root": w.appellation.region.root.name}
            for w in WineProfile.objects.select_related("appellation__region__parent__parent")}
    ids = [i for i, t in zip(sp.ids, sp.types, strict=True) if t == "profile" and i.split(":", 1)[1] in info]
    points = [tuple(sp.position(i)) for i in ids]
    labels = _kmeans(points, K)
    member_of = {node: lab for node, lab in zip(ids, labels, strict=True)}
    groups = []
    for g in sorted(set(labels)):
        members = [node for node, lab in member_of.items() if lab == g]
        wines = [info[m.split(":", 1)[1]] for m in members]
        colour = Counter(w["color"] for w in wines).most_common(1)[0][0]
        groups.append({"id": f"group:{g}", "label": name(wines), "n": len(members), "color": colour})
    return member_of, tuple(groups)


def groups() -> tuple[dict[str, int], list[dict]]:
    """({id de vin: n° de groupe}, [groupes]) ; vide si la carte n'est pas disponible."""
    from django.utils.translation import get_language

    from .space import space

    sp = space()
    if sp is None:
        return {}, []
    member_of, gs = _groups((sp.meta.get("trained"), len(sp.ids)), get_language() or "fr")
    return member_of, list(gs)
