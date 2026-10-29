from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Appellation, Aroma, AromaFamily, Grape, ProfileAroma, Region, WineProfile


def home(request):
    from apps.blindtest.engine import daily_profile

    teaser = None
    if WineProfile.objects.exists():
        profile = daily_profile(timezone.localdate())
        teaser = {
            "color": profile.get_color_display(),
            "color_key": profile.color,
            "aromas": [pa.aroma.name for pa in profile.profile_aromas.select_related("aroma")[:3]],
        }
    stats = {
        "profiles": WineProfile.objects.count(),
        "appellations": Appellation.objects.count(),
        "grapes": Grape.objects.count(),
        "aromas": Aroma.objects.count(),
    }
    return render(request, "home.html", {"teaser": teaser, "stats": stats})


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
    return render(request, "catalog/profile.html", {
        "profile": profile, "siblings": siblings, "neighbours": neighbours,
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
    grape = get_object_or_404(Grape, slug=slug)
    links = (
        grape.profile_links.select_related("profile__appellation__region__parent")
        .order_by("-share", "profile__name")
    )
    aromas = (
        Aroma.objects.filter(profile_links__profile__profile_grapes__grape=grape)
        .annotate(n=Count("profile_links")).select_related("family").order_by("-n", "name")[:12]
    )
    return render(request, "catalog/grape.html", {"grape": grape, "links": links, "aromas": aromas})


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
    return render(request, "catalog/aroma.html", {"aroma": aroma, "links": links})


def sources(request):
    return render(request, "catalog/sources.html")
