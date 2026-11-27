"""Page « Comparer » : deux vins face à face."""

from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.catalog.i18n import tr
from apps.catalog.models import WineProfile
from apps.catalog.text import normalize

from . import compare, compare_svg


def search(request):
    """Vins dont le nom, l'appellation, la région ou un cépage contient tous les mots tapés."""
    words = normalize(request.GET.get("q", "")).split()
    if not words:
        return JsonResponse({"results": []})
    wines = WineProfile.objects.select_related("appellation__region", "appellation__country").prefetch_related(
        "profile_grapes__grape")
    found = []
    for w in wines:
        name = normalize(tr(w.name))
        hay = " ".join([name, normalize(w.appellation.name), normalize(tr(w.appellation.region.name)),
                        normalize(tr(w.appellation.country.name)),
                        *(normalize(pg.grape.name) for pg in w.profile_grapes.all())])
        if all(word in hay for word in words):
            rank = (0 if name.startswith(words[0]) else 1 if words[0] in name else 2, name)
            found.append((rank, {"slug": w.slug, "label": tr(w.name),
                                 "hint": f"{tr(w.appellation.region.name)} · {w.get_color_display().lower()}"}))
    found.sort(key=lambda x: x[0])
    return JsonResponse({"results": [f for _r, f in found[:8]]})


def start(request):
    """Sans paramètre : un duel par défaut. Avec ?a=…&b=… (le formulaire) : l'adresse propre du duel."""
    a, b = request.GET.get("a"), request.GET.get("b")
    if not (a and b):
        a, b = compare.DEFAULT_PAIR
        if WineProfile.objects.filter(slug__in=[a, b]).count() < 2:
            first = list(WineProfile.objects.order_by("slug").values_list("slug", flat=True)[:2])
            if len(first) < 2:
                raise Http404("Pas assez de vins")
            a, b = first
    return redirect(reverse("compare:duel", args=[a, b]))


def duel(request, a, b):
    qs = WineProfile.objects.select_related("appellation__region", "appellation__country").prefetch_related(
        "profile_grapes__grape")
    wa = get_object_or_404(qs, slug=a)
    wb = get_object_or_404(qs, slug=b)
    ctx = {"same": wa.pk == wb.pk}
    if not ctx["same"]:
        d = compare.duel(wa, wb)
        name_a, name_b = compare.short_name(wa), compare.short_name(wb)
        ctx.update(d)
        ctx.update(
            name_a=name_a, name_b=name_b, full_a=tr(wa.name), full_b=tr(wb.name),
            gauge=compare_svg.gauge(d["percent"], d["band"]) if d["percent"] is not None else "",
            radar=compare_svg.radar(d["mouth"], name_a, name_b),
            nose_wide=compare_svg.nose_wide(d["nose"], name_a, name_b),
            nose_narrow=compare_svg.nose_narrow(d["nose"], name_a, name_b),
        )
    else:
        ctx.update(a=wa, b=wb, name_a=tr(wa.name), name_b=tr(wb.name), full_a=tr(wa.name), full_b=tr(wb.name))
    return render(request, "embeddings/compare.html", ctx)
