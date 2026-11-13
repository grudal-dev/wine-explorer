"""Classements des jeux : blind test, chaud-froid, et le total des deux.

Seuls les défis du jour comptent (jamais les parties libres), une ligne par joueur.
Toutes les lignes ont la même forme : username, points, played, wins, + le détail propre au jeu.
"""

from __future__ import annotations

from datetime import date

from django.db.models import Count, Max, Q, Sum

from apps.blindtest.models import Game
from apps.nose.models import HotColdResult

GAMES = ("total", "blindtest", "hotcold")
LIMIT = 20


def _rank(rows: list[dict]) -> list[dict]:
    rows.sort(key=lambda r: (-r["points"], r["username"].lower()))
    return rows[:LIMIT]


def _blindtest_today(day: date) -> dict[str, dict]:
    games = (Game.objects.filter(mode=Game.Mode.DAILY, day=day, user__isnull=False)
             .exclude(status=Game.Status.PLAYING).select_related("user"))
    return {g.user.username: {"username": g.user.username, "points": g.score, "played": 1,
                              "wins": int(g.status == Game.Status.WON), "result": g.get_status_display()}
            for g in games}


def _hotcold_today(day: date) -> dict[str, dict]:
    results = HotColdResult.objects.filter(day=day).select_related("user")
    return {r.user.username: {"username": r.user.username, "points": r.score, "played": 1,
                              "wins": int(r.outcome == HotColdResult.Outcome.WON),
                              "result": r.get_outcome_display(), "guesses": r.guesses}
            for r in results}


def _blindtest_all() -> dict[str, dict]:
    rows = (Game.objects.filter(mode=Game.Mode.DAILY, user__isnull=False)
            .exclude(status=Game.Status.PLAYING).values("user__username")
            .annotate(points=Sum("score"), played=Count("id"),
                      wins=Count("id", filter=Q(status=Game.Status.WON)), best=Max("score")))
    return {r["user__username"]: {"username": r["user__username"], "points": r["points"] or 0,
                                  "played": r["played"], "wins": r["wins"], "best": r["best"]} for r in rows}


def _hotcold_all() -> dict[str, dict]:
    rows = (HotColdResult.objects.values("user__username")
            .annotate(points=Sum("score"), played=Count("id"),
                      wins=Count("id", filter=Q(outcome=HotColdResult.Outcome.WON)), best=Max("score")))
    return {r["user__username"]: {"username": r["user__username"], "points": r["points"] or 0,
                                  "played": r["played"], "wins": r["wins"], "best": r["best"]} for r in rows}


def _total(blind: dict[str, dict], hot: dict[str, dict]) -> list[dict]:
    rows = []
    for name in blind.keys() | hot.keys():
        b, h = blind.get(name), hot.get(name)
        rows.append({
            "username": name,
            "blindtest": b["points"] if b else 0, "hotcold": h["points"] if h else 0,
            "points": (b["points"] if b else 0) + (h["points"] if h else 0),
            "played": (b["played"] if b else 0) + (h["played"] if h else 0),
            "wins": (b["wins"] if b else 0) + (h["wins"] if h else 0),
        })
    return rows


def standings(game: str, day: date) -> dict[str, list[dict]]:
    """{"today": [...], "all_time": [...]} pour « total », « blindtest » ou « hotcold »."""
    if game == "blindtest":
        today, all_time = _blindtest_today(day), _blindtest_all()
        return {"today": _rank(list(today.values())), "all_time": _rank(list(all_time.values()))}
    if game == "hotcold":
        today, all_time = _hotcold_today(day), _hotcold_all()
        return {"today": _rank(list(today.values())), "all_time": _rank(list(all_time.values()))}
    return {
        "today": _rank(_total(_blindtest_today(day), _hotcold_today(day))),
        "all_time": _rank(_total(_blindtest_all(), _hotcold_all())),
    }
