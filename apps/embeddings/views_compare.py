"""Page « Comparer » : deux vins face à face."""

from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.catalog.i18n import tr
from apps.catalog.models import WineProfile

from . import compare, compare_svg


def _choices():
    wines = WineProfile.objects.select_related("appellation__country").order_by("appellation__country__name", "name")
    groups: dict[str, list] = {}
    for w in wines:
        groups.setdefault(tr(w.appellation.country.name), []).append((w.slug, tr(w.name)))
    return sorted(groups.items())


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
    ctx = {"choices": _choices(), "same": wa.pk == wb.pk}
    if not ctx["same"]:
        d = compare.duel(wa, wb)
        name_a, name_b = tr(wa.name), tr(wb.name)
        ctx.update(d)
        ctx.update(
            name_a=name_a, name_b=name_b,
            gauge=compare_svg.gauge(d["percent"], d["band"]) if d["percent"] is not None else "",
            dials=[{**m, "svg": compare_svg.dial(m["a"], m["b"], m["label"], name_a, name_b)} for m in d["mouth"]],
            nose_wide=compare_svg.nose_wide(d["nose"], name_a, name_b),
            nose_narrow=compare_svg.nose_narrow(d["nose"], name_a, name_b),
        )
    else:
        ctx.update(a=wa, b=wb, name_a=tr(wa.name), name_b=tr(wb.name))
    return render(request, "embeddings/compare.html", ctx)
