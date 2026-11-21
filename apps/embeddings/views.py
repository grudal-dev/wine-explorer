from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.catalog.models import Color, Region
from apps.explorer.graph import TYPE_LABELS

from .nodes import cousins, describe
from .space import space

MAP_TYPES = ("profile", "grape", "aroma", "appellation", "region", "molecule")


def taste_map(request):
    sp = space()
    return render(request, "embeddings/map.html", {
        "ready": sp is not None,
        "meta": sp.meta if sp else {},
        "types": [(t, TYPE_LABELS[t]) for t in MAP_TYPES],
        "colors": Color.choices,
        "roots": Region.objects.filter(parent__isnull=True).order_by("name"),
        "focus": request.GET.get("focus", ""),
    })


@require_GET
def api_map(request):
    """Position 2D de chaque entité (projection des vecteurs appris)."""
    sp = space()
    if sp is None:
        return JsonResponse({"nodes": []})
    # Nuances de couleur des vins sur la carte : sucrosité des blancs, tanins des rouges (0 à 5).
    from apps.catalog.models import WineProfile

    from .groups import groups

    member_of, group_list = groups()
    shades = {f"profile:{slug}": {"sweet": sweet, "tannin": tannin, "group": member_of.get(f"profile:{slug}")}
              for slug, sweet, tannin in WineProfile.objects.values_list("slug", "sweetness", "tannin")}
    nodes = []
    for node_id, kind, (x, y) in zip(sp.ids, sp.types, sp.xy, strict=True):
        if kind not in MAP_TYPES:
            continue
        info = describe(node_id)
        if info is None:
            continue  # entité retirée depuis l'entraînement
        info.pop("type_label")
        nodes.append({**info, **shades.get(node_id, {}), "x": x, "y": y})
    return JsonResponse({"nodes": nodes, "groups": group_list})


@require_GET
def api_neighbours(request):
    """Les plus proches voisins d'une entité, pour tracer les traits sur la carte."""
    sp = space()
    node_id = request.GET.get("id", "")
    if sp is None or node_id not in sp:
        return JsonResponse({"neighbours": []})
    kind = node_id.split(":", 1)[0]
    out = [{"id": other, "similarity": round(sim, 3)}
           for other, sim in sp.neighbours(node_id, types=(kind,), k=6)]
    return JsonResponse({"neighbours": out})


@require_GET
def cousins_panel(request, node_id: str):
    """Fragment HTMX : la fiche courte d'une entité et ce qui lui ressemble."""
    info = describe(node_id)
    if info is None:
        raise Http404
    return render(request, "embeddings/_panel.html", {"node": info, "groups": cousins(node_id)})
