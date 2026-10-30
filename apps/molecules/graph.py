"""Graphe en trois colonnes : vin → molécules → éléments naturels.

On part d'une entité (un profil, une molécule ou un élément naturel) et l'on
déroule la chaîne dans les deux sens. Les nœuds portent une « couche »
(0, 1, 2) que le client place en colonnes. Les données sont lues une fois par
version et gardées en mémoire, comme le graphe principal.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache

from django.db.models import Count

from apps.catalog.models import WineProfile
from apps.catalog.text import normalize

from .models import Basis, Molecule, NaturalSource, Occurrence, ProfileMolecule

KIND_COLORS = {
    "epice": "#A4502A", "herbe": "#7D8A5A", "fleur": "#B57BB0", "fruit": "#C2334D",
    "legume": "#6E8B3D", "plante": "#56662D", "arbre": "#6B4A35", "champignon": "#5C5145",
    "aliment": "#C8A27A",
}
MAX_PROFILES = 18


@dataclass
class Data:
    profiles: dict[str, dict]
    molecules: dict[str, dict]
    sources: dict[str, dict]
    # profil → [(molécule, force, base, universel_seul)]
    by_profile: dict[str, list[tuple]] = field(default_factory=lambda: defaultdict(list))
    by_molecule_profiles: dict[str, list[tuple]] = field(default_factory=lambda: defaultdict(list))
    by_molecule_sources: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    by_source: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))


def data_version() -> tuple:
    return (
        ProfileMolecule.objects.count(),
        Occurrence.objects.count(),
        Molecule.objects.count(),
        WineProfile.objects.count(),
    )


@lru_cache(maxsize=2)
def _data(version: tuple) -> Data:
    profiles = {
        p.slug: {"slug": p.slug, "label": p.name, "color": p.color, "url": p.get_absolute_url()}
        for p in WineProfile.objects.only("slug", "name", "color")
    }
    molecules = {
        m.slug: {"slug": m.slug, "label": m.name, "family": m.family, "family_label": m.get_family_display(),
                 "origin": m.origin, "universal": m.universal, "formula": m.formula,
                 "url": m.get_absolute_url()}
        for m in Molecule.objects.all()
    }
    sources = {
        s.slug: {"slug": s.slug, "label": s.name, "kind": s.kind, "kind_label": s.get_kind_display(),
                 "hue": KIND_COLORS[s.kind], "url": s.get_absolute_url()}
        for s in NaturalSource.objects.all()
    }
    d = Data(profiles, molecules, sources)
    for pm in ProfileMolecule.objects.select_related("profile", "molecule").only(
        "strength", "basis", "reasons", "profile__slug", "molecule__slug"
    ):
        only_universal = all(r["basis"] == Basis.UNIVERSAL for r in pm.reasons)
        row = (pm.molecule.slug, pm.strength, pm.basis, only_universal)
        d.by_profile[pm.profile.slug].append(row)
        d.by_molecule_profiles[pm.molecule.slug].append((pm.profile.slug, pm.strength, pm.basis, only_universal))
    for occ in Occurrence.objects.select_related("molecule", "source").only("molecule__slug", "source__slug"):
        d.by_molecule_sources[occ.molecule.slug].append(occ.source.slug)
        d.by_source[occ.source.slug].append(occ.molecule.slug)
    for rows in d.by_profile.values():
        rows.sort(key=lambda r: (-r[1], molecules[r[0]]["label"]))
    for rows in d.by_molecule_profiles.values():
        rows.sort(key=lambda r: (-r[1], profiles[r[0]]["label"]))
    return d


def data() -> Data:
    return _data(data_version())


def reset():
    _data.cache_clear()


# ----------------------------------------------------------------------------
def _node(kind: str, info: dict, layer: int, **extra) -> dict:
    payload = {"id": f"{kind}:{info['slug']}", "label": info["label"], "type": kind, "layer": layer}
    if kind == "profile":
        payload["wine"] = info["color"]
    elif kind == "molecule":
        payload["family"] = info["family"]
        payload["universal"] = info["universal"]
    elif kind == "source":
        payload["hue"] = info["hue"]
    payload.update(extra)
    return {"group": "nodes", "data": payload}


def _edge(a: str, b: str, kind: str, strength: int = 1, basis: str = "") -> dict:
    return {"group": "edges", "data": {
        "id": f"{a}>{b}", "source": a, "target": b, "kind": kind, "strength": strength, "basis": basis,
    }}


def build(kind: str, slug: str, common: bool = False) -> dict | None:
    """Éléments Cytoscape pour l'entité de départ. ``common`` inclut le socle commun."""
    d = data()
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    hidden_common = 0
    truncated = 0

    def keep(row) -> bool:
        return common or not row[3]

    if kind == "profile":
        if slug not in d.profiles:
            return None
        pid = f"profile:{slug}"
        nodes[pid] = _node("profile", d.profiles[slug], 0, root=True)
        for mslug, strength, basis, only_u in d.by_profile.get(slug, []):
            if not keep((mslug, strength, basis, only_u)):
                hidden_common += 1
                continue
            mid = f"molecule:{mslug}"
            nodes[mid] = _node("molecule", d.molecules[mslug], 1, strength=strength)
            edges.append(_edge(pid, mid, "contains", strength, basis))
            for sslug in d.by_molecule_sources.get(mslug, []):
                sid = f"source:{sslug}"
                nodes.setdefault(sid, _node("source", d.sources[sslug], 2))
                edges.append(_edge(mid, sid, "found_in"))

    elif kind == "molecule":
        if slug not in d.molecules:
            return None
        mid = f"molecule:{slug}"
        nodes[mid] = _node("molecule", d.molecules[slug], 1, root=True)
        rows = [r for r in d.by_molecule_profiles.get(slug, []) if keep(r)]
        hidden_common = len(d.by_molecule_profiles.get(slug, [])) - len(rows)
        truncated = max(0, len(rows) - MAX_PROFILES)
        for pslug, strength, basis, _ in rows[:MAX_PROFILES]:
            pid = f"profile:{pslug}"
            nodes[pid] = _node("profile", d.profiles[pslug], 0)
            edges.append(_edge(pid, mid, "contains", strength, basis))
        for sslug in d.by_molecule_sources.get(slug, []):
            sid = f"source:{sslug}"
            nodes[sid] = _node("source", d.sources[sslug], 2)
            edges.append(_edge(mid, sid, "found_in"))

    elif kind == "source":
        if slug not in d.sources:
            return None
        sid = f"source:{slug}"
        nodes[sid] = _node("source", d.sources[slug], 2, root=True)
        # Profils : on agrège par vin la meilleure force sur l'ensemble des molécules.
        best: dict[str, tuple[int, str]] = {}
        per_profile: dict[str, list[tuple]] = defaultdict(list)
        for mslug in d.by_source.get(slug, []):
            mid = f"molecule:{mslug}"
            nodes[mid] = _node("molecule", d.molecules[mslug], 1)
            edges.append(_edge(mid, sid, "found_in"))
            for row in d.by_molecule_profiles.get(mslug, []):
                if not keep(row):
                    continue
                pslug, strength, basis, _ = row
                per_profile[pslug].append((mslug, strength, basis))
                if pslug not in best or strength > best[pslug][0]:
                    best[pslug] = (strength, basis)
        ranked = sorted(best, key=lambda p: (-best[p][0], -len(per_profile[p]), d.profiles[p]["label"]))
        truncated = max(0, len(ranked) - MAX_PROFILES)
        for pslug in ranked[:MAX_PROFILES]:
            pid = f"profile:{pslug}"
            nodes[pid] = _node("profile", d.profiles[pslug], 0)
            for mslug, strength, basis in per_profile[pslug]:
                edges.append(_edge(pid, f"molecule:{mslug}", "contains", strength, basis))
    else:
        return None

    degree: dict[str, int] = defaultdict(int)
    for e in edges:
        degree[e["data"]["source"]] += 1
        degree[e["data"]["target"]] += 1
    for nid, n in nodes.items():
        n["data"]["degree"] = degree[nid]
    ordered = sorted(nodes.values(), key=lambda n: (n["data"]["layer"], -n["data"].get("strength", 0),
                                                   -n["data"]["degree"], n["data"]["label"]))
    counts = defaultdict(int)
    for n in nodes.values():
        counts[n["data"]["type"]] += 1
    return {
        "elements": ordered + edges,
        "stats": {
            "profiles": counts["profile"], "molecules": counts["molecule"], "sources": counts["source"],
            "hidden_common": hidden_common, "truncated": truncated,
        },
    }


def search(q: str, limit: int = 12) -> list[dict]:
    d = data()
    nq = normalize(q)
    if not nq:
        return []
    labels = {"profile": "Vin", "molecule": "Molécule", "source": "Élément naturel"}
    scored = []
    for kind, pool in (("profile", d.profiles), ("molecule", d.molecules), ("source", d.sources)):
        for info in pool.values():
            label = normalize(info["label"])
            if label.startswith(nq):
                rank = 0
            elif nq in label:
                rank = 1
            else:
                continue
            scored.append((rank, len(label), kind, info))
    scored.sort(key=lambda t: (t[0], t[1], t[3]["label"]))
    return [{"id": f"{k}:{i['slug']}", "kind": k, "slug": i["slug"], "label": i["label"], "hint": labels[k]}
            for _, _, k, i in scored[:limit]]


def popular_sources(limit: int = 8) -> list[NaturalSource]:
    """Éléments naturels les plus « connectés », pour les suggestions de départ."""
    return list(NaturalSource.objects.annotate(n=Count("occurrences")).order_by("-n", "name")[:limit])
