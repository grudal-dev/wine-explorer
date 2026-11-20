"""Décors de saison.

Une fête = une fenêtre de dates, une classe `decor-<nom>` sur `<body>` (guirlande sous l'en-tête, logo remplacé,
voir app.css) et un bandeau `templates/partials/_<nom>.html`. Ordre dans l'année, sans chevauchement :

- **Marathon du Médoc** (`medoc`) : un samedi de début septembre, à Pauillac. Date confirmée dans
  `MEDOC_EDITIONS`, sinon estimée (samedi du 2 au 8 septembre) et affichée sans jour précis.
  Décor de J-7 au dimanche.
- **Fête des Vendanges de Montmartre** (`montmartre`) : du mercredi au dimanche autour du deuxième samedi
  d'octobre. Dates confirmées dans `MONTMARTRE_EDITIONS`, sinon estimées et affichées sans jour précis.
  Décor de J-7 au dimanche.
- **Vino novello** (`novello`) : mis en vente en Italie le 30 octobre (décret du 13 août 2012). Décor du
  30 octobre au 9 novembre. Date calculée.
- **Beaujolais nouveau** (`beaujolais`) : troisième jeudi de novembre, décor jusqu'au dimanche J+10. Date calculée.
- **Percée du Vin Jaune** (`vinjaune`, Jura) : fête itinérante sans date ni lieu fixes (31 janvier 2026, 6-7 février
  2027, aucune édition en 2025) : **ajouter chaque année l'édition suivante à `PERCEE_EDITIONS`** d'après
  https://www.percee-du-vin-jaune.com/. Une année absente n'a pas de décor ; la vérification `catalog.W002` le
  rappelle de novembre à janvier. Décor de J-10 au dimanche.

Tout est en heure de Paris. `SEASONAL_DECOR` (variable d'environnement) : `auto` (défaut, selon la date), `off`
(jamais), ou le nom d'un décor (forcé, pour le prévisualiser hors saison : il prend alors l'édition de l'année
en cours, ou la dernière connue pour la Percée).
"""

from dataclasses import dataclass
from datetime import date, timedelta

from django.conf import settings
from django.core import checks
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from . import sections

DECORS = ("medoc", "montmartre", "novello", "beaujolais", "vinjaune")
BEAUJOLAIS_DAYS = 11  # jeudi J → dimanche J+10
NOVELLO_DAYS = 11  # 30 octobre → 9 novembre
PERCEE_LEAD_DAYS = 10  # le bandeau annonce la Percée dix jours avant
LEAD_DAYS = 7  # Médoc et Montmartre : annoncés une semaine avant


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

# Dates annoncées par les organisateurs (consulté le 20/11/2026). Les années absentes sont estimées.
MEDOC_EDITIONS = {
    2025: date(2025, 9, 6),
    2026: date(2026, 9, 5),
    2027: date(2027, 9, 4),
}
MONTMARTRE_EDITIONS = {
    2025: (date(2025, 10, 8), date(2025, 10, 12)),
    2026: (date(2026, 10, 7), date(2026, 10, 11)),
}
MONTMARTRE_FIRST = 1934  # première fête, un an après la plantation du Clos Montmartre (1933)


@dataclass(frozen=True)
class Window:
    start: date  # premier jour de la fête
    end: date  # dernier jour de la fête
    confirmed: bool = True  # dates annoncées (sinon estimées : le bandeau ne donne pas de jour précis)


def _weekday_on_or_after(d: date, weekday: int) -> date:
    return d + timedelta(days=(weekday - d.weekday()) % 7)


def beaujolais_day(year: int) -> date:
    """Troisième jeudi de novembre."""
    return _weekday_on_or_after(date(year, 11, 1), 3) + timedelta(weeks=2)


def medoc_window(year: int) -> Window:
    """Le samedi de la course (et le dimanche) ; estimé au samedi du 2 au 8 septembre."""
    if year in MEDOC_EDITIONS:
        saturday, confirmed = MEDOC_EDITIONS[year], True
    else:
        saturday, confirmed = _weekday_on_or_after(date(year, 9, 2), 5), False
    return Window(saturday, saturday + timedelta(days=1), confirmed)


def montmartre_window(year: int) -> Window:
    """Du mercredi au dimanche ; estimé autour du deuxième samedi d'octobre."""
    if year in MONTMARTRE_EDITIONS:
        return Window(*MONTMARTRE_EDITIONS[year])
    saturday = _weekday_on_or_after(date(year, 10, 1), 5) + timedelta(weeks=1)
    return Window(saturday - timedelta(days=3), saturday + timedelta(days=1), confirmed=False)


def percee_for(today: date) -> Percee | None:
    """L'édition dont la fenêtre de décor contient `today`."""
    edition = PERCEE_EDITIONS.get(today.year)
    if edition and edition.start - timedelta(days=PERCEE_LEAD_DAYS) <= today <= edition.end:
        return edition
    return None


def _in(today: date, window: Window, lead: int) -> bool:
    return window.start - timedelta(days=lead) <= today <= window.end


def current_decor(today: date | None = None) -> str:
    mode = getattr(settings, "SEASONAL_DECOR", "auto")
    if mode == "off" or mode in DECORS:
        return "" if mode == "off" else mode
    today = today or timezone.localdate()
    year = today.year
    if _in(today, medoc_window(year), LEAD_DAYS):
        return "medoc"
    if _in(today, montmartre_window(year), LEAD_DAYS):
        return "montmartre"
    if date(year, 10, 30) <= today < date(year, 10, 30) + timedelta(days=NOVELLO_DAYS):
        return "novello"
    start = beaujolais_day(year)
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
    cat = "catalogue" in on
    mol = "molecules" in on

    def catalog(name, slug):
        return _url(f"catalog:{name}", slug) if cat else ""

    ctx = {"seasonal_decor": decor, "decor_year": today.year}
    if decor == "beaujolais":
        ctx.update({
            "beaujolais_today": today == beaujolais_day(today.year),
            "beaujolais_year": today.year,
            "beaujolais_region_url": catalog("region", "beaujolais"),
            "beaujolais_grape_url": catalog("grape", "gamay"),
        })
    elif decor == "vinjaune":
        edition = percee_for(today) or PERCEE_EDITIONS[max(PERCEE_EDITIONS)]
        ctx.update({
            "percee": edition,
            "percee_now": edition.start <= today <= edition.end,
            "percee_same_month": edition.start.month == edition.end.month,
            "percee_appellation_url": catalog("appellation", "chateau-chalon"),
            "percee_grape_url": catalog("grape", "savagnin"),
            "percee_molecule_url": _url("molecules:molecule", "sotolon") if mol else "",
        })
    elif decor == "medoc":
        window = medoc_window(today.year)
        ctx.update({
            "medoc": window,
            "medoc_now": window.start <= today <= window.end,
            "medoc_appellation_url": catalog("appellation", "pauillac"),
            "medoc_region_url": catalog("region", "medoc"),
            "medoc_grape_url": catalog("grape", "cabernet-sauvignon"),
        })
    elif decor == "montmartre":
        window = montmartre_window(today.year)
        ctx.update({
            "montmartre": window,
            "montmartre_now": window.start <= today <= window.end,
            "montmartre_edition": today.year - MONTMARTRE_FIRST + 1,
            "montmartre_gamay_url": catalog("grape", "gamay"),
            "montmartre_pinot_url": catalog("grape", "pinot-noir"),
        })
    else:  # novello
        ctx.update({
            "novello_today": (today.month, today.day) == (10, 30),
            "novello_molecule_url": _url("molecules:molecule", "acetate-disoamyle") if mol else "",
            "novello_beaujolais_url": catalog("region", "beaujolais"),
        })
    return ctx


def check_percee_calendar(app_configs, **kwargs):
    """De novembre à janvier, rappelle d'ajouter l'édition de la Percée qui vient si elle manque."""
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
