"""Graphe en trois couches : vin → molécules → arômes du vin (vue d'un vin) ou éléments naturels.

On part d'une entité (un profil, une molécule ou un élément naturel) et l'on
déroule la chaîne dans les deux sens. Depuis un vin, la troisième couche est faite des arômes
de ce vin que chaque molécule explique (rotundone → poivre noir) : les éléments naturels, qui
renvoyaient souvent loin du vin (souchet rond, jacquier, truffe noire), restent dans les vues
d'une molécule ou d'un élément naturel. Les nœuds portent une « couche »
(0, 1, 2) que le client place en colonnes. Les données sont lues une fois par
version et gardées en mémoire, comme le graphe principal.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache

from django.db.models import Count
from django.utils.translation import gettext

from apps.catalog.i18n import all_labels, tr
from apps.catalog.models import WineProfile
from apps.catalog.text import normalize

from .models import Basis, ChemicalFamily, Molecule, NaturalSource, Occurrence, ProfileMolecule, Reference

KIND_COLORS = {
    "epice": "#A4502A", "herbe": "#7D8A5A", "fleur": "#B57BB0", "fruit": "#C2334D",
    "legume": "#6E8B3D", "plante": "#56662D", "arbre": "#6B4A35", "champignon": "#5C5145",
    "aliment": "#C8A27A", "espece": "#8FA58A",
}
MAX_PROFILES = 18
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
    # Arôme du vin qui justifie le lien (« caramel » pour le furanéol du tawny), sinon absent.
    link_note: dict[tuple[str, str], tuple[str, str]] = field(default_factory=dict)   # (arôme, couleur)
    # Arômes de chaque vin : identifiant → (intensité, nom, couleur de famille, slug, nom de famille).
    profile_aromas: dict[str, dict[int, tuple]] = field(default_factory=lambda: defaultdict(dict))
    # Arômes du catalogue qu'une molécule explique (descripteurs de molecules.yaml).
    molecule_aromas: dict[str, set[int]] = field(default_factory=lambda: defaultdict(set))
    # Arômes reliés à un élément naturel du même nom (poivre noir → poivre noir), pour la fiche.
    aroma_sources: dict[int, list[str]] = field(default_factory=lambda: defaultdict(list))


COMMON_BASES = {Basis.UNIVERSAL, Basis.COLOR}


def link_tier(reasons: list[dict]) -> str:
    """« universal » : socle commun seul, celui de tous les vins ou de toute une couleur (le diacétyle
    des 84 rouges ne dit rien d'un rouge en particulier) ; sinon « specific »."""
    if {r["basis"] for r in reasons} <= COMMON_BASES:
        return "universal"
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
        m.slug: {"slug": m.slug, "label": m.name, "family": m.family, "family_label": ChemicalFamily(m.family).label,
                 "origin": m.origin, "universal": m.universal, "attack": m.attack, "formula": m.formula, "odor": m.odor,
                 "url": m.get_absolute_url()}
        for m in Molecule.objects.all()
    }
    sources = {
        s.slug: {"slug": s.slug, "label": s.name, "kind": s.kind, "kind_label": NaturalSource.Kind(s.kind).label,
                 "hue": KIND_COLORS[s.kind], "url": s.get_absolute_url(), "imported": s.imported,
                 "aroma": s.aroma_id}
        for s in NaturalSource.objects.all()
    }
    # Couleur d'une molécule : celle de la famille d'arômes de sa première note d'odeur (poivre noir →
    # épices), à défaut de son premier arôme ; sert au bouquet (vue d'un vin).
    from apps.catalog.models import Aroma
    from apps.catalog.text import normalize as _norm

    aroma_hue = {_norm(a.name): a.family.color for a in Aroma.objects.select_related("family")}
    first_hue: dict[str, str] = {}
    for m in Molecule.objects.prefetch_related("aromas__family"):
        notes = [_norm(x) for x in m.odor.split(",") if x.strip()]
        hue = next((aroma_hue[n] for n in notes if n in aroma_hue), None)
        if hue is None:
            hue = next((a.family.color for a in m.aromas.all()), None)
        first_hue[m.slug] = hue or "#2E6E6A"
    for slug, info in molecules.items():
        info["hue"] = first_hue.get(slug, "#2E6E6A")
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
    mol_aromas_by_slug: dict[str, set[int]] = defaultdict(set)
    for mid, mslug, aid in Molecule.aromas.through.objects.values_list("molecule_id", "molecule__slug", "aroma_id"):
        mol_aromas[mid].add(aid)
        mol_aromas_by_slug[mslug].add(aid)
    # Arômes des vins, et pour chaque lien l'arôme commun le plus intense (à égalité, le premier
    # de la molécule par ordre alphabétique, pour un affichage stable).
    from apps.catalog.models import ProfileAroma

    p_int: dict[str, dict[int, tuple[int, str, str]]] = defaultdict(dict)
    for pslug, aid, intensity, aname, ahue, aslug, fname in ProfileAroma.objects.values_list(
        "profile__slug", "aroma_id", "intensity", "aroma__name", "aroma__family__color", "aroma__slug",
        "aroma__family__name",
    ):
        p_int[pslug][aid] = (intensity, aname, ahue)
        d.profile_aromas[pslug][aid] = (intensity, aname, ahue, aslug, fname)
    d.molecule_aromas.update(mol_aromas_by_slug)
    for s in sources.values():
        if s["aroma"]:
            d.aroma_sources[s["aroma"]].append(s["slug"])
    for (pslug, mslug) in d.link_refs:
        common = [p_int[pslug][a] for a in mol_aromas_by_slug[mslug] if a in p_int[pslug]]
        if common:
            _, name, hue = sorted(common, key=lambda x: (-x[0], x[1]))[0]
            d.link_note[(pslug, mslug)] = (name, hue)
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
    tier_rank = {"specific": 0, "universal": 1}
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
    payload = {"id": f"{kind}:{info['slug']}", "label": tr(info["label"]), "type": kind, "layer": layer}
    if kind == "profile":
        payload["wine"] = info["color"]
    elif kind == "molecule":
        payload["family"] = info["family"]
        payload["universal"] = info["universal"]
        payload["att"] = info.get("attack", 2)
        # Première note de l'odeur : « rotundone » ne dit rien, « poivre noir » si.
        payload["odor"] = tr(info.get("odor", "")).split(",")[0].strip()
        payload["hue"] = info.get("hue", "#2E6E6A")
    elif kind == "source":
        payload["hue"] = info["hue"]
        payload["imported"] = info.get("imported", False)
    payload.update(extra)
    return {"group": "nodes", "data": payload}


def _occ_strength(d: "Data", molecule: str, source: str) -> int:
    """Épaisseur d'un lien molécule ↔ élément naturel = niveau de preuve : 3 sourcé par une publication,
    2 vérifié à la main sans notice, 1 importé de Wikidata (aucune force propre n'existe en base)."""
    if (molecule, source) in d.occ_imported:
        return 1
    return 3 if (molecule, source) in d.occ_refs else 2


def _edge(a: str, b: str, kind: str, strength: int = 1, basis: str = "", tier: str = "specific") -> dict:
    return {"group": "edges", "data": {
        "id": f"{a}>{b}", "source": a, "target": b, "kind": kind, "strength": strength, "basis": basis,
        "tier": tier,
    }}


def build(kind: str, slug: str, common: bool | None = None,
          imported: bool = True, max_profiles: int = MAX_PROFILES) -> dict | None:
    """Éléments Cytoscape pour l'entité de départ.

    ``common`` : True ou False force le socle commun ; None (défaut) l'ajoute d'office quand
    un vin a peu de molécules propres, pour qu'aucun graphe ne soit vide.
    """
    d = data()
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    hidden_common = 0
    hidden_sources = 0
    truncated = 0
    aromas_total = aromas_explained = 0

    if common is None:
        if kind == "profile":
            own = [r for r in d.by_profile.get(slug, []) if r[3] == "specific"]
            common = len(own) < AUTO_COMMON_BELOW
        else:
            common = False

    def sources_of(mslug: str) -> list[str]:
        return [x for x in d.by_molecule_sources.get(mslug, [])
                if imported or (mslug, x) not in d.occ_imported]

    def keep(row) -> bool:
        return row[3] == "specific" or common

    if kind == "profile":
        if slug not in d.profiles:
            return None
        pid = f"profile:{slug}"
        nodes[pid] = _node("profile", d.profiles[slug], 0, root=True)
        wine_aromas = d.profile_aromas.get(slug, {})
        for row in d.by_profile.get(slug, []):
            mslug, strength, basis, tier = row
            if not keep(row):
                hidden_common += 1
                continue
            mid = f"molecule:{mslug}"
            extra = {"strength": strength, "tier": tier}
            if note := d.link_note.get((slug, mslug)):
                # La bulle prend la couleur de l'arôme qu'elle explique : le furanéol d'un tawny est caramel.
                extra["note"], extra["hue"] = tr(note[0]), note[1]
                extra["direct"] = True   # reliée par un arôme du vin, pas seulement par cépage, style ou couleur
            nodes[mid] = _node("molecule", d.molecules[mslug], 1, **extra)
            edges.append(_edge(pid, mid, "contains", strength, basis, tier))
            # Troisième couche : les arômes de CE vin que la molécule explique. Deux molécules qui donnent
            # « rose » pointent vers la même étiquette au lieu de répéter le mot dans leurs bulles.
            explained = sorted((aid for aid in d.molecule_aromas.get(mslug, ()) if aid in wine_aromas),
                               key=lambda a: (-wine_aromas[a][0], wine_aromas[a][1]))
            for aid in explained:
                intensity, aname, ahue, aslug, fname = wine_aromas[aid]
                aid_node = f"aroma:{aslug}"
                if aid_node not in nodes:
                    nodes[aid_node] = {"group": "nodes", "data": {
                        "id": aid_node, "label": tr(aname), "type": "aroma", "layer": 2, "hue": ahue,
                        "intensity": intensity, "family": tr(fname), "near": True}}
                edges.append(_edge(mid, aid_node, "evokes", intensity))
        aromas_total = len(wine_aromas)
        aromas_explained = sum(1 for n in nodes.values() if n["data"]["type"] == "aroma")

    elif kind == "molecule":
        if slug not in d.molecules:
            return None
        mid = f"molecule:{slug}"
        nodes[mid] = _node("molecule", d.molecules[slug], 1, root=True)
        rows = [r for r in d.by_molecule_profiles.get(slug, []) if keep(r)]
        hidden_common = len(d.by_molecule_profiles.get(slug, [])) - len(rows)
        truncated = max(0, len(rows) - max_profiles)
        for pslug, strength, basis, tier in rows[:max_profiles]:
            pid = f"profile:{pslug}"
            nodes[pid] = _node("profile", d.profiles[pslug], 0)
            edges.append(_edge(pid, mid, "contains", strength, basis, tier))
        for sslug in sources_of(slug):
            sid = f"source:{sslug}"
            nodes[sid] = _node("source", d.sources[sslug], 2)
            tier = "imported" if (slug, sslug) in d.occ_imported else "specific"
            edges.append(_edge(mid, sid, "found_in", _occ_strength(d, slug, sslug), tier=tier))

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
            edges.append(_edge(mid, sid, "found_in", _occ_strength(d, mslug, slug), tier=tier))
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
        truncated = max(0, len(ranked) - max_profiles)
        for pslug in ranked[:max_profiles]:
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
    tier_rank = {"specific": 0, "universal": 1}
    ordered = sorted(nodes.values(), key=lambda n: (
        n["data"]["layer"], tier_rank.get(n["data"].get("tier", "specific"), 0), -n["data"].get("strength", 0),
        -n["data"]["degree"], n["data"]["label"]))
    # Sources de ce graphe : celles des arêtes affichées, avec le nombre de liens qu'elles appuient.
    cited: dict[str, int] = defaultdict(int)
    for e in edges:
        a, b = e["data"]["source"].split(":", 1)[1], e["data"]["target"].split(":", 1)[1]
        if e["data"]["kind"] == "contains":
            keys = d.link_refs.get((a, b), set())
        elif e["data"]["kind"] == "evokes":
            continue   # la référence du descripteur est déjà comptée sur le lien vin → molécule
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
            "aromas": aromas_explained, "aromas_total": aromas_total,
            "common": bool(common),
        },
    }


def search(q: str, limit: int = 12) -> list[dict]:
    d = data()
    nq = normalize(q)
    if not nq:
        return []
    labels = {"profile": gettext("Vin"), "molecule": gettext("Molécule"), "source": gettext("Élément naturel")}
    scored = []
    for kind, pool in (("profile", d.profiles), ("molecule", d.molecules), ("source", d.sources)):
        for info in pool.values():
            names = [normalize(text) for text in all_labels(info["label"])]
            if any(name.startswith(nq) for name in names):
                rank = 0
            elif any(nq in name for name in names):
                rank = 1
            else:
                continue
            scored.append((rank, len(names[0]), kind, info))
    scored.sort(key=lambda t: (t[0], t[1], t[3]["label"]))
    return [{"id": f"{k}:{i['slug']}", "kind": k, "slug": i["slug"], "label": tr(i["label"]), "hint": labels[k]}
            for _, _, k, i in scored[:limit]]


def popular_sources(limit: int = 8) -> list[NaturalSource]:
    """Éléments naturels les plus « connectés », pour les suggestions de départ."""
    return list(NaturalSource.objects.annotate(n=Count("occurrences")).order_by("-n", "name")[:limit])
