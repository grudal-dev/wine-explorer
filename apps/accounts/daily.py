"""Les défis du jour, vus du joueur : où il en est, qui mène, quand ça change."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from django.utils import timezone

from apps.blindtest.models import Game
from apps.blindtest.views import leaderboard as blindtest_leaderboard
from apps.blindtest.views import owned_games
from apps.nose import hotcold
from apps.nose.models import HotColdResult


def next_reset():
    """Prochain minuit local : les deux défis changent à ce moment-là."""
    now = timezone.localtime()
    tomorrow = datetime.combine(now.date() + timedelta(days=1), time.min)
    return timezone.make_aware(tomorrow, now.tzinfo)


def _best(rows):
    first = next(iter(rows), None)
    return first


def blindtest_card(request, day):
    game = owned_games(request).filter(mode=Game.Mode.DAILY, day=day).first()
    state, points, url = "todo", None, ""
    if game:
        url = game.get_absolute_url()
        state = "playing" if not game.is_over else "done"
        points = game.score if game.is_over else None
    top = _best(blindtest_leaderboard(day, limit=1))
    return {"key": "blindtest", "state": state, "points": points, "url": url,
            "best": {"username": top.user.username, "points": top.score} if top else None}


def hotcold_card(request, day):
    state_data = request.session.get(hotcold.SESSION_KEY) or {}
    today_state = state_data if (state_data.get("mode") == "daily" and state_data.get("day") == day.isoformat()) else {}
    state, points = "todo", None
    if today_state.get("over"):
        state = "done"
        won = today_state["over"] == "won"
        points = hotcold.points(len(today_state["guesses"]), won)
    elif today_state.get("guesses"):
        state = "playing"
    if request.user.is_authenticated:
        mine = HotColdResult.objects.filter(user=request.user, day=day).first()
        if mine:  # le résultat classé fait foi, même si la session a changé
            state, points = "done", mine.score
    top = _best(hotcold.leaderboard(day, limit=1))
    return {"key": "hotcold", "state": state, "points": points, "url": "",
            "best": {"username": top.user.username, "points": top.score} if top else None}


def overview(request, day):
    return {"cards": [blindtest_card(request, day), hotcold_card(request, day)],
            "reset_at": next_reset()}
