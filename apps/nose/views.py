from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.catalog.index import search_aroma
from apps.catalog.models import Aroma, AromaFamily, Color

from .predictor import predict


def _ints(values) -> list[int]:
    out = []
    for v in values:
        for part in str(v).split(","):
            if part.strip().isdigit():
                out.append(int(part))
    return out


def _context(request) -> dict:
    aroma_ids = _ints(request.GET.getlist("a"))
    family_ids = _ints(request.GET.getlist("f"))
    colors = [c for c in request.GET.getlist("c") if c in Color.values]
    # Saisie libre non résolue côté client (sans JavaScript)
    free = request.GET.get("q", "").strip()
    unknown = []
    if free:
        for term in [t for t in free.replace(";", ",").split(",") if t.strip()]:
            hits = search_aroma(term, limit=1, families=True)
            if hits and hits[0].score >= 0.5:
                (aroma_ids if hits[0].kind == "aroma" else family_ids).append(hits[0].pk)
            else:
                unknown.append(term.strip())
    selected = list(Aroma.objects.filter(id__in=aroma_ids).select_related("family"))
    selected_fam = list(AromaFamily.objects.filter(id__in=family_ids))
    result = predict(aroma_ids, family_ids, colors=colors or None, top=5)
    return {
        "selected": selected,
        "selected_families": selected_fam,
        "colors": Color.choices,
        "chosen_colors": colors,
        "result": result,
        "unknown": unknown,
        "has_query": bool(aroma_ids or family_ids),
    }


def nose(request):
    ctx = _context(request)
    ctx["families"] = AromaFamily.objects.prefetch_related("aromas")
    template = "nose/_results.html" if request.htmx else "nose/nose.html"
    return render(request, template, ctx)


@require_GET
def api_aromas(request):
    results = [
        {"kind": m.kind, "pk": m.pk, "label": m.label,
         "kind_label": "Famille" if m.kind == "family" else "Arôme"}
        for m in search_aroma(request.GET.get("q", ""), limit=8, families=True)
    ]
    return JsonResponse({"results": results})
