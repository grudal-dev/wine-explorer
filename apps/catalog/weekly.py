"""Vin de la semaine : un profil type mis en avant du lundi au dimanche, quand aucune fête n'occupe le bandeau.

Choix déterministe (le même pour tous, sans table) : chaque année, les profils sont mélangés avec une graine
fixe et la semaine ISO n puise dans sa réserve de ce tirage ; pas de répétition dans l'année (vérifié
de 2026 à 2040 avec les 138 vins du 20/11/2026).
Le vin de la semaine ne doit rien dévoiler : on saute tout vin qui est, un jour de cette semaine, le défi du
jour du blind test ou du chaud-froid. Le bandeau est aussi masqué sur les pages des deux jeux.

Réglage `WINE_OF_THE_WEEK` (variable d'environnement, vrai par défaut).
"""

import random
from datetime import date, timedelta

from django.conf import settings
from django.core.cache import cache

from .models import WineProfile

GAME_PATHS = ("/blind-test", "/chaud-froid", "/le-nez/chaud-froid")


def week_of(day: date) -> tuple[int, int, date]:
    """(année ISO, semaine ISO, lundi)."""
    iso = day.isocalendar()
    return iso.year, iso.week, day - timedelta(days=day.weekday())


def _daily_wines(monday: date) -> set[str]:
    """Slugs des défis du jour (blind test et chaud-froid) de la semaine."""
    from apps.blindtest.engine import daily_profile

    days = [monday + timedelta(days=i) for i in range(7)]
    slugs = {daily_profile(d).slug for d in days}
    try:
        from apps.embeddings.space import space
        from apps.nose.hotcold import daily_secret

        sp = space()
        slugs |= {daily_secret(d, sp) for d in days}
    except Exception:  # noqa: BLE001 — représentations absentes : pas de chaud-froid à protéger
        pass
    return slugs


def pick_slug(day: date) -> str | None:
    year, week, monday = week_of(day)
    slugs = sorted(WineProfile.objects.values_list("slug", flat=True))
    if not slugs:
        return None
    random.Random(f"terroirs-vin-de-la-semaine-{year}").shuffle(slugs)
    taken = _daily_wines(monday)
    # Chaque semaine a sa propre réserve de `stride` vins dans le tirage de l'année : sauter un défi du
    # jour n'empiète pas sur la semaine suivante (avec 138 vins, deux places par semaine).
    # En dernier recours : les vins que le tirage n'attribue à aucune semaine, puis n'importe lequel.
    stride = max(1, len(slugs) // 53)
    start = (week - 1) * stride
    own = slugs[start:start + stride]
    spare = slugs[53 * stride:]
    if spare:  # chaque semaine commence ailleurs dans la réserve commune, pour ne pas reprendre le même
        r = (week - 1) % len(spare)
        spare = spare[r:] + spare[:r]
    for candidate in [*own, *spare, *slugs]:
        if candidate not in taken:
            return candidate
    return slugs[start % len(slugs)]


def wine_of_the_week(day: date) -> WineProfile | None:
    year, week, _monday = week_of(day)
    key = f"vin-de-la-semaine:{year}-{week}:{WineProfile.objects.count()}"
    slug = cache.get(key)
    if slug is None:
        slug = pick_slug(day) or ""
        cache.set(key, slug, 60 * 60 * 6)
    if not slug:
        return None
    return (WineProfile.objects.select_related("appellation__region__parent", "appellation__country")
            .prefetch_related("profile_aromas__aroma", "profile_grapes__grape").filter(slug=slug).first())


def enabled() -> bool:
    return getattr(settings, "WINE_OF_THE_WEEK", True)
