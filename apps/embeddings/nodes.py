"""Ce qu'il faut pour afficher une entité du graphe : libellé traduit, type, lien, couleur."""

from __future__ import annotations

from apps.catalog.i18n import tr
from apps.explorer.graph import TYPE_LABELS, full_graph
from apps.explorer.views import SINGULAR

from .space import Space, space

# Qui montrer comme « cousins » d'une entité, par type, et combien.
COUSIN_PLAN = {
    "profile": (("profile", 6), ("grape", 4), ("aroma", 5)),
    "grape": (("grape", 5), ("profile", 5), ("aroma", 5), ("region", 3)),
    "aroma": (("aroma", 6), ("profile", 5), ("grape", 4), ("molecule", 3)),
    "region": (("region", 4), ("grape", 5), ("aroma", 5)),
    "appellation": (("appellation", 6), ("grape", 4), ("aroma", 5)),
    "molecule": (("molecule", 5), ("aroma", 5), ("profile", 5), ("source", 4)),
    "source": (("source", 5), ("molecule", 4), ("aroma", 4)),
    "family": (("family", 3), ("aroma", 6)),
}

MIN_SIMILARITY = 0.25  # en dessous, la parenté n'est que du bruit : on ne l'affiche pas


def describe(node_id: str) -> dict | None:
    node = full_graph().nodes.get(node_id)
    if node is None:
        return None
    out = {"id": node.id, "label": tr(node.label), "type": node.type, "url": node.url,
           "type_label": SINGULAR[node.type]}
    if node.type == "profile":
        out["wine"] = node.attrs["color"]
    if "hue" in node.attrs:
        out["hue"] = node.attrs["hue"]
    if "root" in node.attrs:
        out["root"] = node.attrs["root"]
    return out


def _linked(node_id: str) -> set[str]:
    """Voisins directs dans le graphe : un cousin déjà relié n'est pas une découverte."""
    g = full_graph()
    return {e.target if e.source == node_id else e.source
            for e in g.edges if node_id in (e.source, e.target)}


def cousins(node_id: str, sp: Space | None = None) -> list[dict]:
    """Groupes [{label, items: [{…, similarity, percent, linked}]}] des entités les plus proches."""
    sp = sp or space()
    if sp is None or node_id not in sp:
        return []
    kind = node_id.split(":", 1)[0]
    linked = _linked(node_id)
    groups = []
    for other_kind, k in COUSIN_PLAN.get(kind, ()):
        items = []
        for other, sim in sp.neighbours(node_id, types=(other_kind,), k=k):
            info = describe(other)
            if info is None or sim < MIN_SIMILARITY:
                continue
            items.append({**info, "similarity": sim, "percent": round(100 * sim), "linked": other in linked})
        if items:
            groups.append({"kind": other_kind, "label": TYPE_LABELS[other_kind], "items": items})
    return groups
