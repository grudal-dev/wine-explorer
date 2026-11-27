import random
from collections import defaultdict

from django.db.models import Count, Prefetch
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET

from apps.catalog.i18n import tr_reason
from apps.catalog.models import Aroma, ProfileAroma, WineProfile

from . import facts, graph
from .models import (
    Basis,
    ChemicalFamily,
    Molecule,
    NaturalSource,
    Occurrence,
    Origin,
    ProfileMolecule,
    Reference,
)

# Points de départ suggérés : un vin par grande famille de molécules.
STARTERS = [
    ("profile", "cote-rotie-rouge"),
    ("profile", "sancerre-blanc"),
    ("profile", "alsace-gewurztraminer"),
    ("profile", "chateau-chalon-blanc"),
    ("source", "poivre-noir"),
    ("source", "rose-de-damas"),
    ("source", "chene"),
    ("source", "truffe-noire"),
]


def _refs_by_key() -> dict[str, Reference]:
    return {r.key: r for r in Reference.objects.all()}


def _with_refs(reasons: list[dict], refs: dict[str, Reference]) -> list[dict]:
    return [{**r, "label": tr_reason(r["label"]), "reference": refs.get(r.get("ref")),
             "basis_label": Basis(r["basis"]).label} for r in reasons]


def explorer(request):
    start = request.GET.get("depart", "")
    kind, _, slug = start.partition(":")
    if kind not in {"profile", "molecule", "source"} or not slug:
        # Départ par défaut : un vin dont la chaîne est riche et parlante.
        kind, slug = "profile", "cote-rotie-rouge"
        if not WineProfile.objects.filter(slug=slug).exists():
            first = ProfileMolecule.objects.values_list("profile__slug", flat=True).first()
            slug = first or ""
    starters = []
    d = graph.data()
    for k, s in STARTERS:
        pool = {"profile": d.profiles, "source": d.sources, "molecule": d.molecules}[k]
        if s in pool:
            starters.append({"id": f"{k}:{s}", "label": pool[s]["label"], "kind": k})
    random_ids = [f"profile:{p}" for p in d.by_profile]
    return render(request, "molecules/explorer.html", {
        "start": f"{kind}:{slug}" if slug else "",
        "starters": starters,
        "random_ids": random.sample(random_ids, min(len(random_ids), 40)),
        "counts": {
            "molecules": Molecule.objects.count(),
            "sources": NaturalSource.objects.count(),
            "references": Reference.objects.count(),
            "imported": Occurrence.objects.filter(imported=True).count(),
        },
    })


@require_GET
def api_graph(request):
    kind = request.GET.get("kind", "")
    slug = request.GET.get("slug", "")
    raw = request.GET.get("commun", "auto")
    common = None if raw == "auto" else raw in {"1", "true", "on"}
    imported = request.GET.get("wikidata", "1") not in {"0", "false", "off"}
    # Vue « bouquet » d'une molécule (ordinateur) : jusqu'à 32 vins en couronne au lieu de 18 en colonne.
    try:
        max_profiles = max(1, min(int(request.GET.get("vins", graph.MAX_PROFILES)), 60))
    except ValueError:
        max_profiles = graph.MAX_PROFILES
    everything = request.GET.get("tout", "0") in {"1", "true", "on"}
    result = graph.build(kind, slug, common=common, imported=imported, max_profiles=max_profiles,
                         everything=everything)
    if result is None:
        return JsonResponse({"error": "Entité inconnue."}, status=404)
    return JsonResponse(result)


api_graph = cache_page(60 * 5)(api_graph)


@require_GET
def api_search(request):
    return JsonResponse({"results": graph.search(request.GET.get("q", ""))})


@require_GET
def panel(request, node_id: str):
    """Fragment HTMX : fiche de l'entité cliquée dans le graphe moléculaire."""
    kind, _, slug = node_id.partition(":")
    refs = _refs_by_key()
    ctx = {"kind": kind, "node_id": node_id}
    if kind == "molecule":
        mol = get_object_or_404(
            Molecule.objects.prefetch_related("occurrences__source", "occurrences__reference", "aromas"), slug=slug
        )
        ctx["obj"] = mol
        # Tous les vins qui la contiennent, par couleur : la couronne du graphe n'en montre qu'une partie.
        wines = (ProfileMolecule.objects.filter(molecule=mol).select_related("profile")
                 .order_by("-strength", "profile__name"))
        by_color: dict[str, list] = defaultdict(list)
        for pm in wines:
            by_color[pm.profile.color].append(pm)
        plural_color = {"rouge": gettext("Rouges"), "blanc": gettext("Blancs"), "rose": gettext("Rosés")}
        ctx["wines_by_color"] = [(plural_color[c], by_color[c]) for c in ("rouge", "blanc", "rose") if by_color.get(c)]
        ctx["n_wines"] = sum(len(v) for v in by_color.values())
        focus = request.GET.get("vin", "")
        if focus:
            link = ProfileMolecule.objects.filter(molecule=mol, profile__slug=focus).select_related("profile").first()
            if link:
                ctx["link"] = link
                ctx["reasons"] = _with_refs(link.reasons, refs)
    elif kind == "source":
        ctx["obj"] = get_object_or_404(
            NaturalSource.objects.prefetch_related("occurrences__molecule", "occurrences__reference"), slug=slug
        )
    elif kind == "aroma":
        # Un arôme du vin, au bout des traits de la vue d'un vin : quelles molécules l'expliquent ici,
        # et l'élément naturel qui porte la même odeur (poivre noir), pour continuer la promenade.
        aroma = get_object_or_404(Aroma.objects.select_related("family"), slug=slug)
        ctx["obj"] = aroma
        ctx["sources"] = list(NaturalSource.objects.filter(aroma=aroma))
        focus = request.GET.get("vin", "")
        if focus:
            pa = ProfileAroma.objects.filter(profile__slug=focus, aroma=aroma).select_related("profile").first()
            if pa:
                ctx["profile"] = pa.profile
                ctx["intensity"] = (gettext("discret"), gettext("présent"), gettext("dominant"))[pa.intensity - 1]
                ctx["molecules"] = [pm.molecule for pm in ProfileMolecule.objects.filter(
                    profile=pa.profile, molecule__aromas=aroma).select_related("molecule").order_by("-strength")]
    elif kind == "profile":
        profile = get_object_or_404(WineProfile.objects.select_related("appellation"), slug=slug)
        ctx["obj"] = profile
        ctx["links"] = profile.profile_molecules.select_related("molecule")[:12]
    else:
        raise Http404
    return render(request, "molecules/_panel.html", ctx)


def molecule_list(request):
    molecules = Molecule.objects.annotate(
        n_wines=Count("profile_links", distinct=True), n_sources=Count("occurrences", distinct=True)
    )
    families = defaultdict(list)
    for m in molecules:
        families[m.get_origin_display()].append(m)
    ordered = [(label, families[label]) for value, label in Origin.choices if families.get(label)]
    return render(request, "molecules/list.html", {
        "groups": ordered,
        "sources": NaturalSource.objects.annotate(n=Count("occurrences")).order_by("kind", "name"),
        "kinds": NaturalSource.Kind,
    })


def molecule_detail(request, slug):
    mol = get_object_or_404(
        Molecule.objects.prefetch_related(
            "aromas__family", "references",
            Prefetch("occurrences", queryset=Occurrence.objects.select_related("source", "reference")),
        ),
        slug=slug,
    )
    refs = _refs_by_key()
    links = list(
        mol.profile_links.select_related("profile__appellation").order_by("-strength", "profile__name")
    )
    specific = [ln for ln in links if not all(r["basis"] == Basis.UNIVERSAL for r in ln.reasons)]
    for ln in specific:
        ln.reasons_full = _with_refs(ln.reasons, refs)
    cited = {r for ln in specific for r in (x.get("ref") for x in ln.reasons) if r}
    cited |= {o.reference.key for o in mol.occurrences.all() if o.reference}
    cited |= {r.key for r in mol.references.all()}
    return render(request, "molecules/molecule.html", {
        "molecule": mol,
        "links": specific,
        "common_count": len(links) - len(specific),
        "bibliography": sorted((refs[k] for k in cited if k in refs), key=lambda r: (r.authors, r.year or 0)),
        "family_label": ChemicalFamily(mol.family).label,
        "fact": facts.for_molecule(mol.slug),
    })


def source_detail(request, slug):
    src = get_object_or_404(
        NaturalSource.objects.select_related("aroma").prefetch_related(
            Prefetch("occurrences", queryset=Occurrence.objects.select_related("molecule", "reference"))
        ),
        slug=slug,
    )
    mol_ids = [o.molecule_id for o in src.occurrences.all()]
    # Vins reliés par au moins une molécule spécifique (le socle commun, de tous les vins ou de toute
    # une couleur, ne dit rien d'un vin : le beurre ne doit pas lister les 84 rouges).
    per_wine: dict[WineProfile, dict] = {}
    for pm in ProfileMolecule.objects.filter(molecule_id__in=mol_ids).select_related("profile", "molecule"):
        if graph.link_tier(pm.reasons) == "universal":
            continue
        w = per_wine.setdefault(pm.profile, {"profile": pm.profile, "strength": 0, "molecules": []})
        w["strength"] = max(w["strength"], pm.strength)
        w["molecules"].append(pm.molecule)
    wines = sorted(per_wine.values(), key=lambda w: (-w["strength"], -len(w["molecules"]), w["profile"].name))
    return render(request, "molecules/source.html", {"source": src, "wines": wines[:15], "n_wines": len(wines)})


def bibliography(request):
    refs = Reference.objects.annotate(
        n_mol=Count("molecules", distinct=True), n_occ=Count("occurrences", distinct=True)
    )
    return render(request, "molecules/bibliography.html", {"references": refs})


# Étape de la vie du vin où naît la molécule, pour la colonne « Origine » de la fiche imprimable.
ORIGIN_STAGE = {
    "raisin": gettext_lazy("Raisin"), "precurseur": gettext_lazy("Raisin"), "environnement": gettext_lazy("Vigne"),
    "fermentation": gettext_lazy("Fermentation"), "malolactique": gettext_lazy("Fermentation"), "micro": gettext_lazy("Fermentation"),
    "bois": gettext_lazy("Élevage"), "vieillissement": gettext_lazy("Élevage"),
}


@require_GET
def print_sheet(request, slug: str):
    """Fragment HTML : la fiche imprimable d'un vin (A4). Le dessin du bouquet est fait par le
    navigateur (Cytoscape) et posé dans <img data-bouquet> ; le reste vient d'ici, avec les mêmes
    réglages que le graphe affiché (socle commun, Wikidata, tout)."""
    profile = get_object_or_404(
        WineProfile.objects.select_related("appellation__region__parent", "appellation__country")
        .prefetch_related("profile_grapes__grape"),
        slug=slug,
    )
    raw = request.GET.get("commun", "auto")
    common = None if raw == "auto" else raw in {"1", "true", "on"}
    result = graph.build(
        "profile", slug, common=common,
        imported=request.GET.get("wikidata", "1") not in {"0", "false", "off"},
        everything=request.GET.get("tout", "0") in {"1", "true", "on"},
    )
    if result is None:
        raise Http404
    d = graph.data()
    nodes = {e["data"]["id"]: e["data"] for e in result["elements"] if e.get("group") == "nodes"}
    explains: dict[str, list[dict]] = defaultdict(list)
    for e in result["elements"]:
        if e.get("group") == "edges" and e["data"]["kind"] == "evokes":
            a = nodes[e["data"]["target"]]
            explains[e["data"]["source"]].append({"label": a["label"], "intensity": a.get("intensity", 1)})
    refs = _refs_by_key()
    numbers = {r["key"]: i for i, r in enumerate(result["references"], start=1)}
    mols = {m.slug: m for m in Molecule.objects.filter(
        slug__in=[n.split(":", 1)[1] for n, x in nodes.items() if x["type"] == "molecule"])}
    rows = []
    for nid, n in nodes.items():
        if n["type"] != "molecule":
            continue
        mslug = nid.split(":", 1)[1]
        m = mols.get(mslug)
        if m is None:
            continue
        reasons = _with_refs(d.link_reasons.get((slug, mslug), []), refs)
        rows.append({
            "name": n["label"], "hue": n.get("hue", "#2E6E6A"), "formula": m.formula_html,
            "stage": ORIGIN_STAGE.get(m.origin, ""),
            "odor": m.odor, "threshold": m.threshold, "origin": m.get_origin_display(),
            "strength": n.get("strength", 1), "direct": bool(n.get("direct")),
            "universal": n.get("tier") == "universal",
            "explains": sorted(explains.get(nid, []), key=lambda a: -a["intensity"]),
            # Le cépage, le style, la couleur d'abord ; à défaut, l'arôme cité qui l'a fait venir.
            "reasons": [{**r, "n": numbers.get(r.get("ref"))}
                        for r in ([x for x in reasons if x["basis"] != "aroma"] or reasons)],
        })
    rows.sort(key=lambda r: (not r["direct"], r["universal"], -r["strength"],
                             -max([a["intensity"] for a in r["explains"]] or [0]), r["name"]))
    aromas = (ProfileAroma.objects.filter(profile=profile).select_related("aroma__family")
              .order_by("-intensity", "aroma__name"))
    return render(request, "molecules/_print_sheet.html", {
        "profile": profile,
        "grapes": profile.profile_grapes.all().order_by("-share"),
        "aromas": aromas,
        "headline": result["headline"],
        "rows": rows,
        "unexplained": result["unexplained"],
        "references": result["references"],
        "url": request.build_absolute_uri(f"{profile.get_absolute_url()}"),
    })
