"""Décors de saison.

Beaujolais nouveau : mis en vente le troisième jeudi de novembre (0 h). Le décor s'affiche de ce jeudi au
dimanche de la semaine suivante inclus (11 jours), en heure de Paris.

`SEASONAL_DECOR` (variable d'environnement) : `auto` (défaut, selon la date), `off` (jamais),
`beaujolais` (forcé, pour le prévisualiser hors saison).
"""

from datetime import date, timedelta

from django.conf import settings
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from . import sections

BEAUJOLAIS_DAYS = 11  # jeudi J → dimanche J+10


def beaujolais_day(year: int) -> date:
    """Troisième jeudi de novembre."""
    first = date(year, 11, 1)
    first_thursday = first + timedelta(days=(3 - first.weekday()) % 7)
    return first_thursday + timedelta(weeks=2)


def current_decor(today: date | None = None) -> str:
    mode = getattr(settings, "SEASONAL_DECOR", "auto")
    if mode in ("off", "beaujolais"):
        return "" if mode == "off" else mode
    today = today or timezone.localdate()
    start = beaujolais_day(today.year)
    return "beaujolais" if start <= today < start + timedelta(days=BEAUJOLAIS_DAYS) else ""


def _url(name: str, *args) -> str:
    try:
        return reverse(name, args=args)
    except NoReverseMatch:
        return ""


def context(request):
    decor = current_decor()
    if not decor:
        return {"seasonal_decor": ""}
    today = timezone.localdate()
    catalogue = "catalogue" in sections.enabled()
    return {
        "seasonal_decor": decor,
        "beaujolais_today": today == beaujolais_day(today.year),
        "beaujolais_year": today.year,
        "beaujolais_region_url": _url("catalog:region", "beaujolais") if catalogue else "",
        "beaujolais_grape_url": _url("catalog:grape", "gamay") if catalogue else "",
    }
