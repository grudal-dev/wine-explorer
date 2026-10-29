"""Construction et filtrage du graphe des entités du vin.

Nœuds : région, appellation, profil, cépage, arôme, famille aromatique.
Arêtes :
    région       → région parente     (« fait partie de »)
    appellation  → région             (« située en »)
    profil       → appellation        (« produit en »)
    profil       → cépage             (part d'encépagement)
    profil       → arôme              (intensité 1-3)
    arôme        → famille            (« appartient à »)

Quand les profils sont masqués, les appellations sont reliées directement aux
cépages et arômes avec des poids agrégés : la vue reste lisible sans perdre
l'information.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from functools import lru_cache

from apps.catalog.index import data_version
from apps.catalog.models import Appellation, Aroma, Color, Region, WineProfile

NODE_TYPES = ("region", "appellation", "profile", "grape", "aroma", "family")
TYPE_LABELS = {
    "region": "Régions",
    "appellation": "Appellations",
    "profile": "Profils types",
    "grape": "Cépages",
    "aroma": "Arômes",
    "family": "Familles d'arômes",
}
EDGE_LABELS = {
    "part_of": "fait partie de",
    "located_in": "située en",
    "made_in": "produit en",
    "grape": "assemble",
    "aroma": "exprime",
    "family": "appartient à",
}


@dataclass
class Node:
    id: str
    type: str
    label: str
    url: str = ""
    attrs: dict = field(default_factory=dict)


@dataclass
class Edge:
    source: str
    target: str
    kind: str
    weight: float = 1.0

    @property
    def id(self) -> str:
        return f"{self.source}>{self.target}"


@dataclass
class WineGraph:
    nodes: dict[str, Node]
    edges: list[Edge]

    def adjacency(self) -> dict[str, list[tuple[str, Edge]]]:
        adj: dict[str, list[tuple[str, Edge]]] = defaultdict(list)
        for e in self.edges:
            adj[e.source].append((e.target, e))
            adj[e.target].append((e.source, e))
        return adj


def nid(kind: str, slug: str) -> str:
    return f"{kind}:{slug}"


@lru_cache(maxsize=2)
def _full_graph(version: tuple) -> WineGraph:
    nodes: dict[str, Node] = {}
    edges: list[Edge] = []

    for r in Region.objects.select_related("parent"):
        nodes[nid("region", r.slug)] = Node(
            nid("region", r.slug), "region", r.name, r.get_absolute_url(),
            {"root": (r.parent.slug if r.parent_id else r.slug), "kind": r.kind},
        )
        if r.parent_id:
            edges.append(Edge(nid("region", r.slug), nid("region", r.parent.slug), "part_of"))

    for a in Appellation.objects.select_related("region", "region__parent"):
        root = a.region.parent.slug if a.region.parent_id else a.region.slug
        nodes[nid("appellation", a.slug)] = Node(
            nid("appellation", a.slug), "appellation", a.name, a.get_absolute_url(),
            {"root": root, "colors": a.colors, "classification": a.classification},
        )
        edges.append(Edge(nid("appellation", a.slug), nid("region", a.region.slug), "located_in"))

    profiles = WineProfile.objects.select_related(
        "appellation__region__parent"
    ).prefetch_related("profile_grapes__grape", "profile_aromas__aroma__family")
    for p in profiles:
        reg = p.appellation.region
        root = reg.parent.slug if reg.parent_id else reg.slug
        pid = nid("profile", p.slug)
        nodes[pid] = Node(pid, "profile", p.name, p.get_absolute_url(), {
            "root": root, "color": p.color, "style": p.style,
            "price_min": p.price_min, "price_max": p.price_max,
            "appellation": nid("appellation", p.appellation.slug),
        })
        edges.append(Edge(pid, nid("appellation", p.appellation.slug), "made_in"))
        for pg in p.profile_grapes.all():
            g = pg.grape
            gid = nid("grape", g.slug)
            nodes.setdefault(gid, Node(gid, "grape", g.name, g.get_absolute_url(), {"skin": g.skin}))
            edges.append(Edge(pid, gid, "grape", pg.share / 100))
        for pa in p.profile_aromas.all():
            ar = pa.aroma
            aid = nid("aroma", ar.slug)
            nodes.setdefault(aid, Node(aid, "aroma", ar.name, ar.get_absolute_url(), {
                "family": nid("family", ar.family.slug), "hue": ar.family.color,
            }))
            edges.append(Edge(pid, aid, "aroma", pa.intensity))

    for ar in Aroma.objects.select_related("family"):
        aid = nid("aroma", ar.slug)
        fid = nid("family", ar.family.slug)
        nodes.setdefault(fid, Node(fid, "family", ar.family.name, "", {"hue": ar.family.color}))
        if aid in nodes:
            edges.append(Edge(aid, fid, "family"))

    return WineGraph(nodes, edges)


def full_graph() -> WineGraph:
    return _full_graph(data_version())


# ----------------------------------------------------------------------------
@dataclass
class GraphQuery:
    types: tuple[str, ...] = ("region", "appellation", "grape")
    colors: tuple[str, ...] = ()
    root_region: str = ""
    price_max: int | None = None
    min_intensity: int = 2
    min_share: int = 10
    focus: str = ""
    depth: int = 2

    @classmethod
    def from_params(cls, params) -> GraphQuery:
        types = tuple(t for t in params.getlist("types") if t in NODE_TYPES) or cls.types
        colors = tuple(c for c in params.getlist("colors") if c in Color.values)
        price = params.get("price_max")

        def as_int(key, default, lo, hi):
            try:
                return max(lo, min(hi, int(params.get(key, default))))
            except (TypeError, ValueError):
                return default

        return cls(
            types=types,
            colors=colors,
            root_region=params.get("region", ""),
            price_max=int(price) if price and price.isdigit() else None,
            min_intensity=as_int("min_intensity", 2, 1, 3),
            min_share=as_int("min_share", 10, 0, 100),
            focus=params.get("focus", ""),
            depth=as_int("depth", 2, 1, 4),
        )


def _profile_visible(node: Node, q: GraphQuery) -> bool:
    a = node.attrs
    if q.colors and a["color"] not in q.colors:
        return False
    if q.root_region and a["root"] != q.root_region:
        return False
    if q.price_max is not None and a["price_min"] is not None and a["price_min"] > q.price_max:
        return False
    return True


def build_view(q: GraphQuery) -> dict:
    """Retourne les éléments Cytoscape correspondant à la requête."""
    g = full_graph()
    profiles = {k: n for k, n in g.nodes.items() if n.type == "profile" and _profile_visible(n, q)}
    show = set(q.types)

    # 1. Arêtes « logiques » : on part des profils retenus.
    edges: dict[str, Edge] = {}

    def add(e: Edge):
        cur = edges.get(e.id)
        if cur:
            cur.weight += e.weight
        else:
            edges[e.id] = Edge(e.source, e.target, e.kind, e.weight)

    used_apps: set[str] = set()
    for e in g.edges:
        if e.source not in profiles:
            continue
        if e.kind == "aroma" and e.weight < q.min_intensity:
            continue
        if e.kind == "grape" and e.weight * 100 < q.min_share:
            continue
        app_id = profiles[e.source].attrs["appellation"]
        used_apps.add(app_id)
        if e.kind == "made_in":
            if "profile" in show and "appellation" in show:
                add(e)
            continue
        # cépage / arôme : rattachés au profil, ou à l'appellation si profils masqués
        target = e.target
        if g.nodes[target].type == "aroma" and "aroma" not in show and "family" in show:
            target = g.nodes[target].attrs["family"]  # agrégation par famille
        if g.nodes[target].type not in show:
            continue
        src = e.source if "profile" in show else (app_id if "appellation" in show else None)
        if src:
            add(Edge(src, target, e.kind, e.weight))

    regions_used: set[str] = set()
    for e in g.edges:
        if e.kind == "located_in" and e.source in used_apps:
            regions_used.add(e.target)
    for e in g.edges:
        if e.kind == "part_of" and e.source in regions_used:
            regions_used.add(e.target)

    for e in g.edges:
        if e.kind == "located_in" and e.source in used_apps and {"appellation", "region"} <= show:
            add(e)
        elif e.kind == "part_of" and e.source in regions_used and "region" in show:
            add(e)

    # Profils masqués mais régions visibles sans appellation : relier directement.
    if "region" in show and "appellation" not in show and "profile" in show:
        app_region = {e.source: e.target for e in g.edges if e.kind == "located_in"}
        for pid, n in profiles.items():
            add(Edge(pid, app_region[n.attrs["appellation"]], "located_in"))

    # 2. Nœuds présents : extrémités des arêtes retenues (+ isolés utiles).
    present: set[str] = set()
    for e in edges.values():
        present.update((e.source, e.target))
    if "profile" in show:
        present.update(profiles)
    if "appellation" in show:
        present.update(used_apps)
    present = {p for p in present if g.nodes[p].type in show}
    # Familles : rattachées aux seuls arômes visibles.
    if {"aroma", "family"} <= show:
        for e in g.edges:
            if e.kind == "family" and e.source in present:
                add(e)
                present.add(e.target)
    edge_list = [e for e in edges.values() if e.source in present and e.target in present]

    # 3. Focus : voisinage à profondeur n.
    if q.focus and q.focus in present:
        adj: dict[str, set[str]] = defaultdict(set)
        for e in edge_list:
            adj[e.source].add(e.target)
            adj[e.target].add(e.source)
        seen = {q.focus}
        frontier = {q.focus}
        for _ in range(q.depth):
            frontier = {nb for n in frontier for nb in adj[n]} - seen
            seen |= frontier
        present = seen
        edge_list = [e for e in edge_list if e.source in present and e.target in present]

    degree: dict[str, int] = defaultdict(int)
    for e in edge_list:
        degree[e.source] += 1
        degree[e.target] += 1

    elements = []
    for node_id in sorted(present):
        n = g.nodes[node_id]
        data = {"id": n.id, "label": n.label, "type": n.type, "degree": degree[n.id]}
        if "hue" in n.attrs:
            data["hue"] = n.attrs["hue"]
        if n.type == "profile":
            data["wine"] = n.attrs["color"]
        if n.type == "grape":
            data["skin"] = n.attrs["skin"]
        elements.append({"group": "nodes", "data": data})
    for e in edge_list:
        elements.append({"group": "edges", "data": {
            "id": e.id, "source": e.source, "target": e.target, "kind": e.kind,
            "label": EDGE_LABELS[e.kind], "weight": round(e.weight, 2),
        }})
    return {
        "elements": elements,
        "stats": {
            "nodes": len(present),
            "edges": len(edge_list),
            "by_type": {t: sum(1 for p in present if g.nodes[p].type == t) for t in NODE_TYPES},
        },
    }


def shortest_path(a: str, b: str) -> list[dict] | None:
    """Plus court chemin entre deux entités dans le graphe complet (BFS)."""
    g = full_graph()
    if a not in g.nodes or b not in g.nodes:
        return None
    adj = g.adjacency()
    prev: dict[str, tuple[str, Edge] | None] = {a: None}
    queue = deque([a])
    while queue:
        cur = queue.popleft()
        if cur == b:
            break
        for nb, edge in adj[cur]:
            # On évite de traverser les familles : chemins plus parlants.
            if nb not in prev and (g.nodes[nb].type != "family" or nb == b):
                prev[nb] = (cur, edge)
                queue.append(nb)
    if b not in prev:
        return None
    steps = []
    cur = b
    while prev[cur] is not None:
        parent, edge = prev[cur]
        steps.append({"from": parent, "to": cur, "edge": edge})
        cur = parent
    steps.reverse()
    out = [{"node": _node_dict(g.nodes[a])}]
    for s in steps:
        e = s["edge"]
        forward = e.source == s["from"]
        out.append({
            "edge": {"id": e.id, "kind": e.kind, "label": EDGE_LABELS[e.kind], "forward": forward},
            "node": _node_dict(g.nodes[s["to"]]),
        })
    return out


def _node_dict(n: Node) -> dict:
    return {"id": n.id, "label": n.label, "type": n.type, "url": n.url}


def search_nodes(q: str, limit: int = 10) -> list[dict]:
    from apps.catalog.text import normalize

    g = full_graph()
    nq = normalize(q)
    if not nq:
        return []
    scored = []
    for n in g.nodes.values():
        label = normalize(n.label)
        if label.startswith(nq):
            scored.append((0, len(label), n))
        elif nq in label:
            scored.append((1, len(label), n))
    scored.sort(key=lambda t: (t[0], t[1], t[2].label))
    return [_node_dict(n) | {"type_label": TYPE_LABELS[n.type]} for _, _, n in scored[:limit]]


def reset():
    _full_graph.cache_clear()
