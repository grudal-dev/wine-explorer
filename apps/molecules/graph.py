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

from .models import Basis, Molecule, NaturalSource, Occurrence, ProfileMolecule, Reference

KIND_COLORS = {
    "epice": "#A4502A", "herbe": "#7D8A5A", "fleur": "#B57BB0", "fruit": "#C2334D",
    "legume": "#6E8B3D", "plante": "#56662D", "arbre": "#6B4A35", "champignon": "#5C5145",
    "aliment": "#C8A27A", "espece": "#8FA58A",
}
MAX_PROFILES = 18
MAX_SOURCES_PER_MOLECULE = 4   # en partant d'un vin ; la fiche de la molécule les liste toutes
AUTO_COMMON_BELOW = 6          # socle commun ajouté d'office sous ce nombre de molécules


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
    # Références qui justifient chaque arête, et notices bibliographiques.
    link_refs: dict[tuple[str, str], set[str]] = field(default_factory=lambda: defaultdict(set))
    occ_refs: dict[tuple[str, str], str] = field(default_factory=dict)
    occ_imported: set[tuple[str, str]] = field(default_factory=set)
    refs: dict[str, dict] = field(default_factory=dict)


def link_tier(reasons: list[dict]) -> str:
    """« universal » : socle commun seul ; « family » : repli par famille ; sinon « specific »."""
    bases = {r["basis"] for r in reasons}
    if bases <= {Basis.UNIVERSAL}:
        return "universal"
    if bases <= {Basis.UNIVERSAL, Basis.FAMILY}:
        return "family"
    return "specific"


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
                 "hue": KIND_COLORS[s.kind], "url": s.get_absolute_url(), "imported": s.imported}
        for s in NaturalSource.objects.all()
    }
    d = Data(profiles, molecules, sources)
    for pm in ProfileMolecule.objects.select_related("profile", "molecule").only(
        "strength", "basis", "reasons", "profile__slug", "molecule__slug"
    ):
        tier = link_tier(pm.reasons)
        d.by_profile[pm.profile.slug].append((pm.molecule.slug, pm.strength, pm.basis, tier))
        d.by_molecule_profiles[pm.molecule.slug].append((pm.profile.slug, pm.strength, pm.basis, tier))
        d.link_refs[(pm.profile.slug, pm.molecule.slug)] = {r["ref"] for r in pm.reasons if r.get("ref")}
    # Ordre des éléments naturels d'une molécule : celui qui porte le même nom qu'un de ses
    # descripteurs (poivre noir pour la rotundone), puis ceux qu'une note commente, puis les autres.
    mol_aromas: dict[int, set[int]] = defaultdict(set)
    for mid, aid in Molecule.aromas.through.objects.values_list("molecule_id", "aroma_id"):
        mol_aromas[mid].add(aid)
    occs = list(Occurrence.objects.select_related("molecule", "source", "reference").only(
        "molecule__slug", "source__slug", "source__aroma_id", "source__name", "reference__key", "imported", "note"
    ))
    occs.sort(key=lambda o: (o.imported, o.source.aroma_id not in mol_aromas[o.molecule_id], not o.note,
                             o.source.name))
    for occ in occs:
        d.by_molecule_sources[occ.molecule.slug].append(occ.source.slug)
        if occ.imported:
            d.occ_imported.add((occ.molecule.slug, occ.source.slug))
        if occ.reference_id:
            d.occ_refs[(occ.molecule.slug, occ.source.slug)] = occ.reference.key
        d.by_source[occ.source.slug].append(occ.molecule.slug)
    for r in Reference.objects.all():
        d.refs[r.key] = {"key": r.key, "short": r.short, "authors": r.authors, "year": r.year,
                         "title": r.title, "container": r.container, "link": r.link}
    tier_rank = {"specific": 0, "family": 1, "universal": 2}
    for rows in d.by_profile.values():
        rows.sort(key=lambda r: (tier_rank[r[3]], -r[1], molecules[r[0]]["label"]))
    for rows in d.by_molecule_profiles.values():
        rows.sort(key=lambda r: (tier_rank[r[3]], -r[1], profiles[r[0]]["label"]))
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
        payload["imported"] = info.get("imported", False)
    payload.update(extra)
    return {"group": "nodes", "data": payload}


def _edge(a: str, b: str, kind: str, strength: int = 1, basis: str = "", tier: str = "specific") -> dict:
    return {"group": "edges", "data": {
        "id": f"{a}>{b}", "source": a, "target": b, "kind": kind, "strength": strength, "basis": basis,
        "tier": tier,
    }}


def build(kind: str, slug: str, common: bool | None = None, family: bool = True,
          imported: bool = True) -> dict | None:
    """Éléments Cytoscape pour l'entité de départ.

    ``family`` inclut les liens déduits d'une seule famille d'arômes (affichés en retrait).
    ``common`` : True ou False force le socle commun ; None (défaut) l'ajoute d'office quand
    un vin a peu de molécules propres, pour qu'aucun graphe ne soit vide.
    """
    d = data()
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    hidden_common = 0
    hidden_sources = 0
    truncated = 0

    if common is None:
        if kind == "profile":
            own = [r for r in d.by_profile.get(slug, []) if r[3] == "specific" or (r[3] == "family" and family)]
            common = len(own) < AUTO_COMMON_BELOW
        else:
            common = False

    def sources_of(mslug: str) -> list[str]:
        return [x for x in d.by_molecule_sources.get(mslug, [])
                if imported or (mslug, x) not in d.occ_imported]

    def keep(row) -> bool:
        tier = row[3]
        return (tier == "specific") or (tier == "family" and family) or (tier == "universal" and common)

    if kind == "profile":
        if slug not in d.profiles:
            return None
        pid = f"profile:{slug}"
        nodes[pid] = _node("profile", d.profiles[slug], 0, root=True)
        for row in d.by_profile.get(slug, []):
            mslug, strength, basis, tier = row
            if not keep(row):
                hidden_common += 1
                continue
            mid = f"molecule:{mslug}"
            nodes[mid] = _node("molecule", d.molecules[mslug], 1, strength=strength, tier=tier)
            edges.append(_edge(pid, mid, "contains", strength, basis, tier))
            srcs = sources_of(mslug)
            # Les éléments déjà présents (partagés par plusieurs molécules) passent en premier.
            srcs = sorted(srcs, key=lambda x: (f"source:{x}" not in nodes, srcs.index(x)))
            hidden_sources += max(0, len(srcs) - MAX_SOURCES_PER_MOLECULE)
            for sslug in srcs[:MAX_SOURCES_PER_MOLECULE]:
                sid = f"source:{sslug}"
                nodes.setdefault(sid, _node("source", d.sources[sslug], 2))
                edges.append(_edge(mid, sid, "found_in",
                                   tier="imported" if (mslug, sslug) in d.occ_imported else "specific"))

    elif kind == "molecule":
        if slug not in d.molecules:
            return None
        mid = f"molecule:{slug}"
        nodes[mid] = _node("molecule", d.molecules[slug], 1, root=True)
        rows = [r for r in d.by_molecule_profiles.get(slug, []) if keep(r)]
        hidden_common = len(d.by_molecule_profiles.get(slug, [])) - len(rows)
        truncated = max(0, len(rows) - MAX_PROFILES)
        for pslug, strength, basis, tier in rows[:MAX_PROFILES]:
            pid = f"profile:{pslug}"
            nodes[pid] = _node("profile", d.profiles[pslug], 0)
            edges.append(_edge(pid, mid, "contains", strength, basis, tier))
        for sslug in sources_of(slug):
            sid = f"source:{sslug}"
            nodes[sid] = _node("source", d.sources[sslug], 2)
            tier = "imported" if (slug, sslug) in d.occ_imported else "specific"
            edges.append(_edge(mid, sid, "found_in", tier=tier))

    elif kind == "source":
        if slug not in d.sources:
            return None
        sid = f"source:{slug}"
        nodes[sid] = _node("source", d.sources[slug], 2, root=True)
        # Profils : on agrège par vin la meilleure force sur l'ensemble des molécules.
        best: dict[str, tuple[int, str]] = {}
        per_profile: dict[str, list[tuple]] = defaultdict(list)
        for mslug in d.by_source.get(slug, []):
            if not imported and (mslug, slug) in d.occ_imported:
                continue
            mid = f"molecule:{mslug}"
            nodes[mid] = _node("molecule", d.molecules[mslug], 1)
            tier = "imported" if (mslug, slug) in d.occ_imported else "specific"
            edges.append(_edge(mid, sid, "found_in", tier=tier))
            for row in d.by_molecule_profiles.get(mslug, []):
                if not keep(row):
                    continue
                pslug, strength, basis, tier = row
                per_profile[pslug].append((mslug, strength, basis, tier))
                if pslug not in best or strength > best[pslug][0]:
                    best[pslug] = (strength, basis)
        def rank(p):
            specific = sum(r[3] == "specific" for r in per_profile[p])
            return (-best[p][0], -specific, -len(per_profile[p]), d.profiles[p]["label"])

        ranked = sorted(best, key=rank)
        truncated = max(0, len(ranked) - MAX_PROFILES)
        for pslug in ranked[:MAX_PROFILES]:
            pid = f"profile:{pslug}"
            nodes[pid] = _node("profile", d.profiles[pslug], 0)
            for mslug, strength, basis, tier in per_profile[pslug]:
                edges.append(_edge(pid, f"molecule:{mslug}", "contains", strength, basis, tier))
    else:
        return None

    degree: dict[str, int] = defaultdict(int)
    for e in edges:
        degree[e["data"]["source"]] += 1
        degree[e["data"]["target"]] += 1
    for nid, n in nodes.items():
        n["data"]["degree"] = degree[nid]
    tier_rank = {"specific": 0, "family": 1, "universal": 2}
    ordered = sorted(nodes.values(), key=lambda n: (
        n["data"]["layer"], tier_rank.get(n["data"].get("tier", "specific"), 0), -n["data"].get("strength", 0),
        -n["data"]["degree"], n["data"]["label"]))
    # Sources de ce graphe : celles des arêtes affichées, avec le nombre de liens qu'elles appuient.
    cited: dict[str, int] = defaultdict(int)
    for e in edges:
        a, b = e["data"]["source"].split(":", 1)[1], e["data"]["target"].split(":", 1)[1]
        if e["data"]["kind"] == "contains":
            keys = d.link_refs.get((a, b), set())
        else:
            keys = {d.occ_refs[(a, b)]} if (a, b) in d.occ_refs else set()
        for k in keys:
            cited[k] += 1
    references = sorted(
        ({**d.refs[k], "links": n} for k, n in cited.items() if k in d.refs),
        key=lambda r: (-r["links"], r["authors"], r["year"] or 0),
    )
    counts = defaultdict(int)
    for n in nodes.values():
        counts[n["data"]["type"]] += 1
    return {
        "elements": ordered + edges,
        "references": references,
        "stats": {
            "profiles": counts["profile"], "molecules": counts["molecule"], "sources": counts["source"],
            "hidden_common": hidden_common, "truncated": truncated, "hidden_sources": hidden_sources,
            "common": bool(common), "family": family,
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
