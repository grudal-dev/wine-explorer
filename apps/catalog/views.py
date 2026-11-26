from django.db.models import Count, Prefetch
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from .grapes import MERGED
from .i18n import tr
from .models import Appellation, Aroma, AromaFamily, Grape, ProfileAroma, Region, WineProfile


def home(request):
    from django.utils import translation

    # Une adresse par langue : le français vit sur « / », l'anglais sur « /en/ ». Seule la page d'accueil
    # envoie vers l'anglais, d'après le choix déjà fait (cookie) ou la langue du navigateur. Les robots,
    # qui n'envoient pas de préférence, voient le français ; les autres pages ne bougent jamais.
    if translation.get_language_from_request(request, check_path=False) == "en" and request.LANGUAGE_CODE != "en":
        with translation.override("en"):
            return redirect(reverse("home"))
    from apps.blindtest.engine import daily_profile

    teaser = None
    if WineProfile.objects.exists():
        profile = daily_profile(timezone.localdate())
        teaser = {
            "color": profile.get_color_display(),
            "color_key": profile.color,
            "aromas": [tr(pa.aroma.name) for pa in profile.profile_aromas.select_related("aroma")[:3]],
        }
    stats = {
        "profiles": WineProfile.objects.count(),
        "appellations": Appellation.objects.count(),
        "grapes": Grape.objects.count(),
        "aromas": Aroma.objects.count(),
    }
    from apps.accounts.daily import overview
    from apps.accounts.rankings import standings

    today = timezone.localdate()
    return render(request, "home.html", {
        "teaser": teaser, "stats": stats, "daily": overview(request, today),
        "podium": standings("total", today)["today"][:3],
    })


def index(request):
    regions = (
        Region.objects.filter(parent__isnull=True)
        .prefetch_related(
            Prefetch("appellations", queryset=Appellation.objects.annotate(n=Count("profiles"))),
            Prefetch(
                "children",
                queryset=Region.objects.prefetch_related(
                    Prefetch("appellations", queryset=Appellation.objects.annotate(n=Count("profiles")))
                ),
            ),
        )
        .order_by("name")
    )
    return render(request, "catalog/index.html", {"regions": regions})


def _profiles_qs():
    return WineProfile.objects.select_related("appellation__region__parent").prefetch_related(
        "profile_grapes__grape", "profile_aromas__aroma__family"
    )


def profile_detail(request, slug):
    profile = get_object_or_404(_profiles_qs(), slug=slug)
    siblings = _profiles_qs().filter(appellation=profile.appellation).exclude(pk=profile.pk)
    # Profils proches : arômes partagés
    aroma_ids = [pa.aroma_id for pa in profile.profile_aromas.all()]
    neighbours = (
        WineProfile.objects.exclude(pk=profile.pk)
        .filter(profile_aromas__aroma_id__in=aroma_ids)
        .annotate(shared=Count("profile_aromas"))
        .order_by("-shared", "name")[:6]
    )
    molecules = [
        pm for pm in profile.profile_molecules.select_related("molecule")
        if any(r["basis"] != "universal" for r in pm.reasons)
    ]
    return render(request, "catalog/profile.html", {
        "profile": profile, "siblings": siblings, "neighbours": neighbours, "molecules": molecules[:8],
        "molecules_total": len(molecules),
    })


def appellation_detail(request, slug):
    app = get_object_or_404(Appellation.objects.select_related("region__parent"), slug=slug)
    profiles = _profiles_qs().filter(appellation=app)
    nearby = (
        Appellation.objects.filter(region=app.region).exclude(pk=app.pk).order_by("name")
    )
    return render(request, "catalog/appellation.html", {
        "appellation": app, "profiles": profiles, "nearby": nearby,
    })


def region_detail(request, slug):
    region = get_object_or_404(Region.objects.select_related("parent"), slug=slug)
    region_ids = [region.id, *region.children.values_list("id", flat=True)]
    appellations = (
        Appellation.objects.filter(region_id__in=region_ids)
        .select_related("region").annotate(n=Count("profiles")).order_by("name")
    )
    grapes = (
        Grape.objects.filter(profile_links__profile__appellation__region_id__in=region_ids)
        .annotate(n=Count("profile_links", distinct=True)).order_by("-n", "name")[:12]
    )
    return render(request, "catalog/region.html", {
        "region": region, "appellations": appellations, "grapes": grapes,
        "children": region.children.all(),
    })


def grape_list(request):
    grapes = Grape.objects.annotate(n=Count("profile_links")).order_by("skin", "name")
    return render(request, "catalog/grapes.html", {"grapes": grapes})


def grape_detail(request, slug):
    grape = Grape.objects.filter(slug=slug).first()
    if grape is None:
        # Ancienne fiche fusionnée (Rolle → Vermentino) ou nom local : redirection permanente.
        merged = MERGED.get(slug)
        target = Grape.objects.filter(slug=merged).first() if merged else None
        if target is None:
            target = next((g for g in Grape.objects.only("slug", "synonyms")
                           if any(slugify(s) == slug for s in g.synonyms or [])), None)
        if target is None:
            raise Http404
        return redirect(target.get_absolute_url(), permanent=True)
    links = (
        grape.profile_links.select_related("profile__appellation__region__parent")
        .order_by("-share", "profile__name")
    )
    aromas = (
        Aroma.objects.filter(profile_links__profile__profile_grapes__grape=grape)
        .annotate(n=Count("profile_links")).select_related("family").order_by("-n", "name")[:12]
    )
    return render(request, "catalog/grape.html", {"grape": grape, "links": links, "aromas": aromas,
                                                  "markers": _grape_markers(grape)})


def _grape_markers(grape) -> list[dict]:
    """Molécules dont ce cépage est un marqueur sourcé (le linalol du Muscat à petits grains), lues dans
    les raisons des liens vin → molécule : la plus forte d'abord."""
    from apps.molecules.models import ProfileMolecule

    best: dict[str, dict] = {}
    names = {grape.name.lower(), *(s.lower() for s in grape.synonyms or [])}
    for pm in ProfileMolecule.objects.filter(profile__profile_grapes__grape=grape).select_related("molecule"):
        for r in pm.reasons:
            if r.get("basis") != "grape" or r["label"].split(" (", 1)[0].lower() not in names:
                continue
            cur = best.get(pm.molecule.slug)
            if cur is None or r["strength"] > cur["strength"]:
                best[pm.molecule.slug] = {"molecule": pm.molecule, "strength": r["strength"]}
    return sorted(best.values(), key=lambda x: (-x["strength"], x["molecule"].name))


def aroma_list(request):
    families = AromaFamily.objects.prefetch_related(
        Prefetch("aromas", queryset=Aroma.objects.annotate(n=Count("profile_links")))
    )
    return render(request, "catalog/aromas.html", {"families": families})


def aroma_detail(request, slug):
    aroma = get_object_or_404(Aroma.objects.select_related("family"), slug=slug)
    links = (
        ProfileAroma.objects.filter(aroma=aroma)
        .select_related("profile__appellation__region__parent")
        .order_by("-intensity", "profile__name")
    )
    return render(request, "catalog/aroma.html", {
        "aroma": aroma, "links": links,
        "molecules": aroma.molecules.all(), "natural_sources": aroma.natural_sources.all(),
    })


def sources(request):
    return render(request, "catalog/sources.html")
