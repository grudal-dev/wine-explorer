"""Règles du blind test.

Le joueur voit la robe (couleur, style), la structure en bouche et quelques
arômes. Il doit reconstituer la fiche complète du vin : région, appellation
et cépages principaux. Chaque essai est une saisie libre résolue vers une
entité ; chaque essai qui ne fait rien découvrir dévoile un indice
supplémentaire.
"""

from __future__ import annotations

import hashlib
import math
import random
import re
from dataclasses import dataclass
from datetime import date

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.catalog.index import search_guess
from apps.catalog.models import Appellation, Grape, Region, WineProfile

from .models import Game, Guess

MAIN_GRAPE_THRESHOLD = 20  # % minimal pour qu'un cépage soit à trouver
AROMAS_START = 3
AROMAS_STEP = 3

CLUES = [
    ("aromas", "D'autres arômes"),
    ("service", "Service et garde"),
    ("price", "Prix indicatif"),
    ("pairings", "Accords"),
    ("description", "Commentaire du sommelier"),
    ("region_initial", "Initiale de la région"),
    ("appellation_shape", "Forme du nom"),
]

COMMON_WORDS = {"petit", "gros", "blanc", "noir", "gris", "fer", "vin", "rose"}


# ---------------------------------------------------------------------------
# Choix du vin
# ---------------------------------------------------------------------------
def daily_profile(day: date) -> WineProfile:
    ids = list(WineProfile.objects.order_by("id").values_list("id", flat=True))
    if not ids:
        raise WineProfile.DoesNotExist("Aucun profil chargé (lancer load_seed).")
    digest = hashlib.sha256(f"terroirs-{day.isoformat()}".encode()).hexdigest()
    return WineProfile.objects.get(pk=ids[int(digest, 16) % len(ids)])


def random_profile(color: str = "", exclude: list[int] | None = None) -> WineProfile:
    qs = WineProfile.objects.all()
    if color:
        qs = qs.filter(color=color)
    ids = list(qs.exclude(pk__in=exclude or []).values_list("id", flat=True)) or list(
        qs.values_list("id", flat=True)
    )
    if not ids:
        raise WineProfile.DoesNotExist("Aucun profil disponible.")
    return WineProfile.objects.get(pk=random.choice(ids))


def new_game(*, mode: str, user=None, session_key: str = "", session_games=(),
             color: str = "") -> Game:
    if mode == Game.Mode.DAILY:
        today = timezone.localdate()
        if user is not None:
            existing = Game.objects.filter(user=user, mode=mode, day=today).first()
        else:
            existing = Game.objects.filter(
                public_id__in=list(session_games), user__isnull=True, mode=mode, day=today
            ).first()
        if existing:
            return existing
        profile, day = daily_profile(today), today
    else:
        recent = []
        if user is not None:
            recent = list(user.games.values_list("profile_id", flat=True)[:15])
        profile, day = random_profile(color, recent), None
    return Game.objects.create(
        user=user, session_key=session_key if user is None else "", profile=profile,
        mode=mode, day=day, max_attempts=settings.BLINDTEST_MAX_ATTEMPTS,
    )


# ---------------------------------------------------------------------------
# Cible
# ---------------------------------------------------------------------------
@dataclass
class Target:
    profile: WineProfile
    appellation: Appellation
    region: Region  # région racine
    subregion: Region | None
    main_grapes: list[Grape]
    minor_grapes: list[Grape]

    @classmethod
    def of(cls, profile: WineProfile) -> Target:
        app = profile.appellation
        reg = app.region
        links = list(profile.profile_grapes.select_related("grape"))
        main = [pg.grape for pg in links if pg.share >= MAIN_GRAPE_THRESHOLD]
        if not main and links:
            main = [links[0].grape]
        minor = [pg.grape for pg in links if pg.grape not in main]
        return cls(
            profile=profile, appellation=app, region=reg.root,
            subregion=reg if reg.parent_id else None, main_grapes=main, minor_grapes=minor,
        )

    def slots(self) -> list[dict]:
        out = [
            {"key": "region", "label": "Région", "answer": self.region.name},
            {"key": "appellation", "label": "Appellation", "answer": self.appellation.name},
        ]
        for g in self.main_grapes:
            out.append({"key": f"grape:{g.id}", "label": "Cépage", "answer": g.name})
        return out


# ---------------------------------------------------------------------------
# Géographie
# ---------------------------------------------------------------------------
def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(
        (lon2 - lon1) / 2
    ) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def bearing_label(src: tuple[float, float], dst: tuple[float, float]) -> str:
    """Direction pour aller de src vers dst, en huit secteurs."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*src, *dst))
    x = math.sin(lon2 - lon1) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
    deg = (math.degrees(math.atan2(x, y)) + 360) % 360
    labels = ["au nord", "au nord-est", "à l'est", "au sud-est",
              "au sud", "au sud-ouest", "à l'ouest", "au nord-ouest"]
    return labels[int((deg + 22.5) // 45) % 8]


def _coords(obj) -> tuple[float, float] | None:
    if obj.lat is None or obj.lng is None:
        return None
    return (obj.lat, obj.lng)


def distance_hint(guessed, target_app: Appellation) -> str:
    a, b = _coords(guessed), _coords(target_app)
    if not a or not b:
        return ""
    km = haversine_km(a, b)
    if km < 15:
        return "Vous y êtes presque : moins de 15 km."
    return f"Le vin est à environ {round(km, -1):.0f} km {bearing_label(a, b)}."


# ---------------------------------------------------------------------------
# Indices
# ---------------------------------------------------------------------------
def mask_text(text: str, target: Target) -> str:
    words = {target.appellation.name, target.region.name}
    if target.subregion:
        words.add(target.subregion.name)
    for g in Grape.objects.only("name", "synonyms"):
        for label in [g.name, *g.synonyms]:
            words.add(label)
            first = label.split()[0]
            if len(first) > 4 and first.lower() not in COMMON_WORDS:
                words.add(first)
    for part in re.split(r"[\s-]+", target.appellation.name):
        if len(part) > 4 and part.lower() not in COMMON_WORDS:
            words.add(part)
    pattern = "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
    return re.sub(rf"\b(?:{pattern})\b", "▒▒▒", text, flags=re.IGNORECASE)


def appellation_shape(name: str) -> str:
    return " ".join(
        (w[0] + "·" * (len(w) - 1)) if w.lower() not in {"de", "du", "des", "et", "la", "le"} else w
        for w in re.split(r"(\s|-)", name) if w.strip() and w != "-"
    )


def tasting_sheet(game: Game) -> dict:
    """Tout ce que le joueur a le droit de voir à cet instant."""
    p = game.profile
    t = Target.of(p)
    over = game.is_over
    revealed = len(CLUES) if over else game.clues_revealed
    unlocked = {key for key, _ in CLUES[:revealed]}

    aroma_links = list(p.profile_aromas.select_related("aroma__family"))
    n_aromas = AROMAS_START + (AROMAS_STEP if "aromas" in unlocked else 0)
    aromas = [
        {"name": pa.aroma.name, "intensity": pa.intensity, "family": pa.aroma.family.name,
         "hue": pa.aroma.family.color}
        for pa in aroma_links[:n_aromas]
    ]
    clues = []
    for key, title in CLUES[:revealed]:
        if key == "aromas":
            continue
        if key == "service":
            body = f"Servir à {p.serving_temp}. Garde : {p.aging_min} à {p.aging_max} ans."
        elif key == "price":
            body = f"Entre {p.price_min} et {p.price_max} € la bouteille."
        elif key == "pairings":
            body = ", ".join(p.pairings).capitalize() + "."
        elif key == "description":
            body = p.description if over else mask_text(p.description, t)
        elif key == "region_initial":
            body = f"La région commence par « {t.region.name[0]} »."
        else:
            body = appellation_shape(t.appellation.name)
        clues.append({"key": key, "title": title, "body": body})

    found = game.found or {}
    slots = []
    for s in t.slots():
        is_found = bool(found.get(s["key"]))
        slots.append({**s, "found": is_found, "show": is_found or over})

    return {
        "color": p.get_color_display(),
        "color_key": p.color,
        "style": p.get_style_display(),
        "structure": p.structure,
        "aromas": aromas,
        "aromas_hidden": max(0, len(aroma_links) - len(aromas)),
        "clues": clues,
        "next_clue": CLUES[revealed][1] if revealed < len(CLUES) else None,
        "slots": slots,
        "grapes_total": len(t.main_grapes),
        "minor_grapes": [g.name for g in t.minor_grapes] if over else [],
    }


# ---------------------------------------------------------------------------
# Essais
# ---------------------------------------------------------------------------
class GuessError(ValueError):
    pass


def _score(game: Game) -> int:
    if game.status == Game.Status.WON:
        return max(100, 1000 - 90 * (game.attempts_used - 1) - 40 * game.clues_revealed)
    return 25 * sum(1 for v in (game.found or {}).values() if v)


@transaction.atomic
def play(game: Game, raw: str, choice: str = "") -> Guess:
    """Joue un essai. `choice` (« kind:pk ») permet de lever une ambiguïté."""
    game = Game.objects.select_for_update().get(pk=game.pk)
    if game.is_over:
        raise GuessError("La partie est terminée.")
    raw = (raw or "").strip()[:120]
    if not raw and not choice:
        raise GuessError("Saisissez une région, une appellation ou un cépage.")

    match = None
    if choice and ":" in choice:
        kind, pk = choice.split(":", 1)
        match = next((m for m in search_guess(raw or pk, limit=20)
                      if m.kind == kind and str(m.pk) == pk), None)
        if match is None and kind in {"appellation", "region", "grape"} and pk.isdigit():
            model = {"appellation": Appellation, "region": Region, "grape": Grape}[kind]
            obj = model.objects.filter(pk=pk).first()
            if obj:
                from apps.catalog.text import Match
                match = Match(kind, obj.pk, obj.name, 1.0)
    if match is None:
        matches = search_guess(raw, limit=3)
        if not matches or matches[0].score < 0.5:
            raise GuessError(f"« {raw} » ne correspond à aucune région, appellation ou cépage connu.")
        match = matches[0]

    if game.guesses.filter(kind=match.kind, value=str(match.pk)).exists():
        raise GuessError(f"Vous avez déjà proposé « {match.label} ».")

    t = Target.of(game.profile)
    found = dict(game.found or {})
    verdict, feedback, counted = _evaluate(match, t, found)

    guess = Guess.objects.create(
        game=game, raw=raw or match.label, kind=match.kind, value=str(match.pk),
        label=match.label, verdict=verdict, feedback=feedback, counted=counted,
    )

    game.found = found
    required = {s["key"] for s in t.slots()}
    if required <= {k for k, v in found.items() if v}:
        game.status = Game.Status.WON
    elif counted and verdict != Guess.Verdict.HIT:
        if game.clues_revealed < len(CLUES):
            game.clues_revealed += 1
        if game.attempts_used >= game.max_attempts:
            game.status = Game.Status.LOST
    if game.is_over:
        game.finished_at = timezone.now()
        game.score = _score(game)
    game.save()
    return guess


def abandon(game: Game) -> None:
    if game.is_over:
        return
    game.status = Game.Status.ABANDONED
    game.finished_at = timezone.now()
    game.score = 0
    game.save(update_fields=["status", "finished_at", "score"])


def _evaluate(match, t: Target, found: dict) -> tuple[str, str, bool]:
    V = Guess.Verdict
    if match.kind in {"color", "style"}:
        return V.INFO, "La robe et le style sont déjà visibles sur la fiche : cet essai n'est pas compté.", False

    if match.kind == "appellation":
        if match.pk == t.appellation.id:
            found["appellation"] = True
            found["region"] = True
            return V.HIT, f"C'est bien un {t.appellation.name} !", True
        guessed = Appellation.objects.select_related("region", "region__parent").get(pk=match.pk)
        hint = distance_hint(guessed, t.appellation)
        if guessed.region.root.id == t.region.id:
            found["region"] = True
            same_sub = t.subregion and guessed.region_id == t.subregion.id
            prefix = "Même sous-région, mais autre appellation." if same_sub else \
                "Bonne région, mais pas la bonne appellation."
            return V.CLOSE, f"{prefix} {hint}".strip(), True
        if t.profile.color not in (guessed.colors or []):
            hint = f"{hint} Et cette appellation ne produit pas de {t.profile.get_color_display().lower()} ici.".strip()
        return V.MISS, hint or "Ce n'est pas cette appellation.", True

    if match.kind == "region":
        guessed = Region.objects.select_related("parent").get(pk=match.pk)
        if guessed.id == t.region.id:
            already = found.get("region")
            found["region"] = True
            return V.HIT if not already else V.INFO, f"Oui, nous sommes en {t.region.name}.", not already
        if t.subregion and guessed.id == t.subregion.id:
            found["region"] = True
            return V.HIT, f"Exactement : {t.subregion.name}, en {t.region.name}.", True
        if guessed.parent_id == t.region.id:
            found["region"] = True
            return V.CLOSE, f"Bonne région ({t.region.name}), mais pas cette sous-région.", True
        return V.MISS, distance_hint(guessed, t.appellation) or "Pas cette région.", True

    if match.kind == "grape":
        key = f"grape:{match.pk}"
        if any(g.id == match.pk for g in t.main_grapes):
            found[key] = True
            return V.HIT, f"{match.label} fait bien partie de l'encépagement principal.", True
        if any(g.id == match.pk for g in t.minor_grapes):
            return V.CLOSE, f"{match.label} est présent, mais en petite proportion.", True
        grape = Grape.objects.get(pk=match.pk)
        return V.MISS, f"Pas de {grape.name} dans ce vin.", True

    raise GuessError("Type d'essai non pris en charge.")


def suggest(q: str) -> list[dict]:
    labels = {"appellation": "Appellation", "region": "Région", "grape": "Cépage",
              "color": "Couleur", "style": "Style"}
    return [{"kind": m.kind, "pk": m.pk, "label": m.label, "kind_label": labels.get(m.kind, "")}
            for m in search_guess(q, limit=8)]
