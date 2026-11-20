"""Décors de saison.

- **Beaujolais nouveau** : mis en vente le troisième jeudi de novembre. Décor de ce jeudi au dimanche de la
  semaine suivante inclus (11 jours). Date calculée : revient seul chaque année.
- **Percée du Vin Jaune** (Jura) : fête itinérante d'un week-end, fin janvier ou début février, où l'on met en
  perce les premiers tonneaux d'un millésime de vin jaune. Ni la date ni le village ne suivent de règle (31 janvier
  2026, 6-7 février 2027, aucune édition en 2025) : **ajouter chaque année l'édition suivante à
  `PERCEE_EDITIONS`** d'après https://www.percee-du-vin-jaune.com/. Une année absente n'a pas de décor, et la
  vérification `catalog.W002` le rappelle à partir de novembre. Décor des dix jours qui précèdent jusqu'au dimanche.

Tout est en heure de Paris. `SEASONAL_DECOR` (variable d'environnement) : `auto` (défaut, selon la date), `off`
(jamais), `beaujolais` ou `vinjaune` (forcé, pour prévisualiser hors saison ; le vin jaune prend la dernière
édition connue).
"""

from dataclasses import dataclass
from datetime import date, timedelta

from django.conf import settings
from django.core import checks
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from . import sections

DECORS = ("beaujolais", "vinjaune")
BEAUJOLAIS_DAYS = 11  # jeudi J → dimanche J+10
PERCEE_LEAD_DAYS = 10  # le bandeau annonce la fête dix jours avant


@dataclass(frozen=True)
class Percee:
    start: date  # samedi
    end: date  # dimanche
    place: str
    vintage: int  # millésime mis en perce


# Source : site officiel (www.percee-du-vin-jaune.com), consulté le 20/11/2026.
PERCEE_EDITIONS = {
    2026: Percee(date(2026, 1, 31), date(2026, 2, 1), "Lons-le-Saunier", 2019),
    2027: Percee(date(2027, 2, 6), date(2027, 2, 7), "Arlay", 2020),
}


def beaujolais_day(year: int) -> date:
    """Troisième jeudi de novembre."""
    first = date(year, 11, 1)
    first_thursday = first + timedelta(days=(3 - first.weekday()) % 7)
    return first_thursday + timedelta(weeks=2)


def percee_for(today: date) -> Percee | None:
    """L'édition dont la fenêtre de décor contient `today`."""
    edition = PERCEE_EDITIONS.get(today.year)
    if edition and edition.start - timedelta(days=PERCEE_LEAD_DAYS) <= today <= edition.end:
        return edition
    return None


def current_decor(today: date | None = None) -> str:
    mode = getattr(settings, "SEASONAL_DECOR", "auto")
    if mode == "off" or mode in DECORS:
        return "" if mode == "off" else mode
    today = today or timezone.localdate()
    start = beaujolais_day(today.year)
    if start <= today < start + timedelta(days=BEAUJOLAIS_DAYS):
        return "beaujolais"
    if percee_for(today):
        return "vinjaune"
    return ""


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
    on = sections.enabled()
    catalogue = "catalogue" in on
    ctx = {"seasonal_decor": decor}
    if decor == "beaujolais":
        ctx.update({
            "beaujolais_today": today == beaujolais_day(today.year),
            "beaujolais_year": today.year,
            "beaujolais_region_url": _url("catalog:region", "beaujolais") if catalogue else "",
            "beaujolais_grape_url": _url("catalog:grape", "gamay") if catalogue else "",
        })
    else:
        edition = percee_for(today) or PERCEE_EDITIONS[max(PERCEE_EDITIONS)]
        ctx.update({
            "percee": edition,
            "percee_now": edition.start <= today <= edition.end,
            "percee_same_month": edition.start.month == edition.end.month,
            "percee_appellation_url": _url("catalog:appellation", "chateau-chalon") if catalogue else "",
            "percee_grape_url": _url("catalog:grape", "savagnin") if catalogue else "",
            "percee_molecule_url": _url("molecules:molecule", "sotolon") if "molecules" in on else "",
        })
    return ctx


def check_percee_calendar(app_configs, **kwargs):
    """À partir de novembre, rappelle d'ajouter l'édition de l'an prochain si elle manque."""
    today = timezone.localdate()
    upcoming = today.year + 1 if today.month >= 11 else today.year
    if today.month not in (11, 12, 1) or upcoming in PERCEE_EDITIONS:
        return []
    return [checks.Warning(
        f"Percée du Vin Jaune {upcoming} absente du calendrier : pas de décor cette année-là.",
        hint="Ajouter l'édition (dates, village, millésime) à PERCEE_EDITIONS dans apps/catalog/seasons.py, "
             "d'après https://www.percee-du-vin-jaune.com/.",
        id="catalog.W002",
    )]
