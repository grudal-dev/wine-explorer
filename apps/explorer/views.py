from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET

from apps.catalog.models import (
    Appellation,
    Aroma,
    AromaFamily,
    Color,
    Grape,
    Region,
    WineProfile,
)

from .graph import (
    NODE_TYPES,
    TYPE_LABELS,
    GraphQuery,
    build_view,
    full_graph,
    search_nodes,
    shortest_path,
)

PRESETS = [
    {"key": "terroirs", "label": "Géographie", "types": ["region", "appellation"],
     "help": "Régions, sous-régions et appellations."},
    {"key": "encepagement", "label": "Encépagement", "types": ["region", "appellation", "grape"],
     "help": "Quels cépages pour quelles appellations."},
    {"key": "aromes", "label": "Arômes", "types": ["appellation", "aroma", "family"],
     "help": "Les descripteurs dominants de chaque appellation."},
    {"key": "complet", "label": "Tout", "types": list(NODE_TYPES),
     "help": "Profils types et toutes leurs relations. Dense : filtrez ou centrez sur un nœud."},
]


def explorer(request):
    roots = Region.objects.filter(parent__isnull=True).order_by("name")
    return render(request, "explorer/explorer.html", {
        "presets": PRESETS,
        "types": [(t, TYPE_LABELS[t]) for t in NODE_TYPES],
        "colors": Color.choices,
        "roots": roots,
        "focus": request.GET.get("focus", ""),
    })


@require_GET
def api_graph(request):
    return JsonResponse(build_view(GraphQuery.from_params(request.GET)))


@require_GET
def api_search(request):
    return JsonResponse({"results": search_nodes(request.GET.get("q", ""))})


@require_GET
def api_path(request):
    path = shortest_path(request.GET.get("a", ""), request.GET.get("b", ""))
    if path is None:
        return JsonResponse({"path": None, "message": "Aucun chemin entre ces deux entités."})
    return JsonResponse({"path": path})


SINGULAR = {
    "region": "Région", "appellation": "Appellation", "profile": "Profil type",
    "grape": "Cépage", "aroma": "Arôme", "family": "Famille d'arômes",
}

MODELS = {
    "region": Region, "appellation": Appellation, "profile": WineProfile,
    "grape": Grape, "aroma": Aroma, "family": AromaFamily,
}


@require_GET
def node_panel(request, node_id: str):
    """Fragment HTMX : fiche de l'entité sélectionnée dans le graphe."""
    kind, _, slug = node_id.partition(":")
    model = MODELS.get(kind)
    if model is None:
        raise Http404
    try:
        obj = model.objects.get(slug=slug)
    except model.DoesNotExist as exc:
        raise Http404 from exc
    g = full_graph()
    adj = g.adjacency()
    neighbours = {}
    for other, edge in adj.get(node_id, []):
        n = g.nodes[other]
        neighbours.setdefault(n.type, []).append(
            {"id": n.id, "label": n.label, "w": edge.weight, "type": n.type})
    groups = [
        (TYPE_LABELS[t], sorted(neighbours[t], key=lambda x: (-x["w"], x["label"]))[:14],
         len(neighbours[t]))
        for t in NODE_TYPES if t in neighbours
    ]
    return render(request, "explorer/_panel.html", {
        "obj": obj, "kind": kind, "node_id": node_id, "kind_label": SINGULAR[kind],
        "groups": groups,
    })


api_graph = cache_page(60 * 5)(api_graph)
