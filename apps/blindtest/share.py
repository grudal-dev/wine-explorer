"""Le résultat d'une partie, prêt à partager (façon Wordle) et la série de jours joués."""

from __future__ import annotations

from datetime import date, timedelta

from django.conf import settings

from .models import Game, Guess

# Numéro du défi : jours écoulés depuis le premier défi du jour, le 1ᵉʳ septembre 2026 (n° 1).
FIRST_DAY = date(2026, 9, 1)
MARKS = {Guess.Verdict.HIT: "🟩", Guess.Verdict.CLOSE: "🟨", Guess.Verdict.MISS: "🟥"}


def number(day: date) -> int:
    return (day - FIRST_DAY).days + 1


def grid(game: Game) -> str:
    """Une pastille par essai compté : 🟩 trouvé, 🟨 proche, 🟥 raté ; ⬜ pour les essais non joués."""
    marks = [MARKS.get(g.verdict, "") for g in game.guesses.all() if g.counted]
    marks = [m for m in marks if m]
    if game.status == Game.Status.WON:
        return "".join(marks)
    return "".join(marks) + "⬜" * max(0, game.max_attempts - len(marks))


def text(game: Game, url: str) -> str:
    """« Wine Explorer n° 87 · 4/8 » + la grille + le lien. Jamais le nom du vin : il gâcherait le jeu."""
    name = settings.SITE_NAME
    used = len([g for g in game.guesses.all() if g.counted])
    score = f"{used}/{game.max_attempts}" if game.status == Game.Status.WON else f"X/{game.max_attempts}"
    daily = game.mode == Game.Mode.DAILY and game.day
    head = f"{name} n° {number(game.day)} · {score}" if daily else f"{name} · {score}"
    return f"{head}\n{grid(game)}\n{url}"


def streak(days, today: date) -> int:
    """Jours d'affilée avec un défi du jour terminé, jusqu'à aujourd'hui (ou hier, si aujourd'hui reste à jouer)."""
    played = set(days)
    day = today if today in played else today - timedelta(days=1)
    n = 0
    while day in played:
        n += 1
        day -= timedelta(days=1)
    return n


def streak_for(games, today: date) -> int:
    days = (games.filter(mode=Game.Mode.DAILY).exclude(status=Game.Status.PLAYING)
            .values_list("day", flat=True))
    return streak((d for d in days if d), today)
