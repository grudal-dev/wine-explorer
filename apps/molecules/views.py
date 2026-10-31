import random
from collections import defaultdict

from django.db.models import Count, Prefetch
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET

from apps.catalog.models import WineProfile

from . import graph
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
    return [{**r, "reference": refs.get(r.get("ref")), "basis_label": Basis(r["basis"]).label} for r in reasons]


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
    family = request.GET.get("famille", "1") not in {"0", "false", "off"}
    imported = request.GET.get("wikidata", "1") not in {"0", "false", "off"}
    result = graph.build(kind, slug, common=common, family=family, imported=imported)
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
    })


def source_detail(request, slug):
    src = get_object_or_404(
        NaturalSource.objects.select_related("aroma").prefetch_related(
            Prefetch("occurrences", queryset=Occurrence.objects.select_related("molecule", "reference"))
        ),
        slug=slug,
    )
    mol_ids = [o.molecule_id for o in src.occurrences.all()]
    # Vins reliés par au moins une molécule spécifique (le socle commun ne dit rien d'un vin).
    per_wine: dict[WineProfile, dict] = {}
    for pm in ProfileMolecule.objects.filter(molecule_id__in=mol_ids).select_related("profile", "molecule"):
        if all(r["basis"] == Basis.UNIVERSAL for r in pm.reasons):
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
