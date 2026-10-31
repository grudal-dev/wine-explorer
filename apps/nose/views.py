from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.catalog.index import search_aroma
from apps.catalog.models import Aroma, AromaFamily, Color

from . import sensory
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
    sense_keys = [k for v in request.GET.getlist("s") for k in v.split(",") if k in sensory.BY_KEY]
    # Saisie libre non résolue côté client (sans JavaScript)
    free = request.GET.get("q", "").strip()
    unknown = []
    if free:
        for term in [t for t in free.replace(";", ",").split(",") if t.strip()]:
            exact = sensory.exact(term)
            if exact:
                sense_keys.append(exact.key)
                continue
            hits = search_aroma(term, limit=1, families=True)
            senses = sensory.search(term, limit=1)
            if hits and hits[0].score >= 0.5:
                (aroma_ids if hits[0].kind == "aroma" else family_ids).append(hits[0].pk)
            elif senses:
                sense_keys.append(senses[0].key)
            else:
                unknown.append(term.strip())
    selected = list(Aroma.objects.filter(id__in=aroma_ids).select_related("family"))
    selected_fam = list(AromaFamily.objects.filter(id__in=family_ids))
    chosen_senses = sensory.clean(sense_keys)
    result = predict(aroma_ids, family_ids, colors=colors or None, senses=[t.key for t in chosen_senses], top=5)
    return {
        "selected": selected,
        "selected_families": selected_fam,
        "colors": Color.choices,
        "chosen_colors": colors,
        "result": result,
        "unknown": unknown,
        "has_query": bool(aroma_ids or family_ids or chosen_senses),
        "selected_senses": chosen_senses,
        "sense_groups": sensory.grouped(),
    }


def nose(request):
    ctx = _context(request)
    ctx["families"] = AromaFamily.objects.prefetch_related("aromas")
    template = "nose/_results.html" if request.htmx else "nose/nose.html"
    return render(request, template, ctx)


@require_GET
def api_aromas(request):
    q = request.GET.get("q", "")
    senses = [
        {"kind": "sense", "pk": t.key, "label": t.label, "axis": t.axis,
         "kind_label": "Bouche" if t.axis != "style" else "Style"}
        for t in sensory.search(q, limit=3)
    ]
    aromas = [
        {"kind": m.kind, "pk": m.pk, "label": m.label,
         "kind_label": "Famille" if m.kind == "family" else "Arôme"}
        for m in search_aroma(q, limit=8, families=True)
    ]
    # Un terme sensoriel exact passe devant ; sinon les arômes d'abord.
    hit = sensory.exact(q)
    exact = [s for s in senses if hit and s["pk"] == hit.key]
    results = (exact + aromas + [s for s in senses if s not in exact])[:9]
    return JsonResponse({"results": results})
