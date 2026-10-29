from django.conf import settings
from django.contrib import messages
from django.db.models import Avg, Count, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.catalog.models import Color, WineProfile

from . import engine
from .models import Game

SESSION_GAMES = "blindtest_games"


def _session_key(request) -> str:
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key


def _owner_kwargs(request) -> dict:
    if request.user.is_authenticated:
        return {"user": request.user}
    return {"session_key": _session_key(request), "user": None}


def _get_game(request, public_id) -> Game:
    game = get_object_or_404(
        Game.objects.select_related("profile__appellation__region__parent"), public_id=public_id
    )
    if game.user_id:
        owner = request.user.is_authenticated and game.user_id == request.user.id
    else:
        owner = str(game.public_id) in request.session.get(SESSION_GAMES, [])
    if not owner and not game.is_over:
        raise Http404  # on ne joue pas la partie d'un autre
    game.is_owner = owner
    return game


def leaderboard(day=None, limit=10):
    day = day or timezone.localdate()
    return (
        Game.objects.filter(mode=Game.Mode.DAILY, day=day, user__isnull=False)
        .exclude(status=Game.Status.PLAYING)
        .select_related("user").order_by("-score", "finished_at")[:limit]
    )


def owned_games(request):
    if request.user.is_authenticated:
        return Game.objects.filter(user=request.user)
    return Game.objects.filter(user__isnull=True,
                               public_id__in=request.session.get(SESSION_GAMES, []))


def home(request):
    recent = owned_games(request).select_related("profile")[:6]
    today = timezone.localdate()
    daily = owned_games(request).filter(mode=Game.Mode.DAILY, day=today).first()
    return render(request, "blindtest/home.html", {
        "recent": recent, "daily": daily, "board": leaderboard(today),
        "colors": Color.choices, "max_attempts": settings.BLINDTEST_MAX_ATTEMPTS,
    })


@require_POST
def start(request):
    mode = request.POST.get("mode", Game.Mode.FREE)
    if mode not in Game.Mode.values:
        mode = Game.Mode.FREE
    color = request.POST.get("color", "")
    owner = _owner_kwargs(request)
    try:
        game = engine.new_game(
            mode=mode, user=owner.get("user"), session_key=owner.get("session_key", ""),
            session_games=request.session.get(SESSION_GAMES, []),
            color=color if color in Color.values else "",
        )
    except WineProfile.DoesNotExist as exc:  # pas de données chargées
        messages.error(request, f"Impossible de lancer une partie : {exc}")
        return redirect("blindtest:home")
    if game.user_id is None:
        ids = request.session.get(SESSION_GAMES, [])
        if str(game.public_id) not in ids:
            request.session[SESSION_GAMES] = [*ids[-49:], str(game.public_id)]
    return redirect(game)


def game_view(request, public_id):
    game = _get_game(request, public_id)
    return render(request, "blindtest/game.html", _game_context(game))


def _game_context(game: Game, error: str = "") -> dict:
    return {
        "game": game,
        "sheet": engine.tasting_sheet(game),
        "guesses": game.guesses.all(),
        "error": error,
    }


@require_POST
def guess(request, public_id):
    game = _get_game(request, public_id)
    if not game.is_owner:
        raise Http404
    error = ""
    try:
        engine.play(game, request.POST.get("q", ""), request.POST.get("choice", ""))
    except engine.GuessError as exc:
        error = str(exc)
    game.refresh_from_db()
    game.is_owner = True
    if request.htmx:
        return render(request, "blindtest/_board.html", _game_context(game, error))
    if error:
        messages.warning(request, error)
    return redirect(game)


@require_POST
def give_up(request, public_id):
    game = _get_game(request, public_id)
    if game.is_owner:
        engine.abandon(game)
    return redirect(game)


@require_GET
def suggest(request):
    return JsonResponse({"results": engine.suggest(request.GET.get("q", ""))})


def stats_for(user):
    qs = Game.objects.filter(user=user).exclude(status=Game.Status.PLAYING)
    agg = qs.aggregate(
        played=Count("id"), won=Count("id", filter=Q(status=Game.Status.WON)),
        avg=Avg("score"),
    )
    agg["rate"] = round(100 * agg["won"] / agg["played"]) if agg["played"] else 0
    by_region = (
        qs.values("profile__appellation__region__parent__name", "profile__appellation__region__name")
        .annotate(n=Count("id"), w=Count("id", filter=Q(status=Game.Status.WON)))
    )
    regions: dict[str, list[int]] = {}
    for row in by_region:
        name = row["profile__appellation__region__parent__name"] or row["profile__appellation__region__name"]
        cur = regions.setdefault(name, [0, 0])
        cur[0] += row["n"]
        cur[1] += row["w"]
    agg["regions"] = sorted(
        ({"name": k, "played": v[0], "won": v[1], "rate": round(100 * v[1] / v[0])}
         for k, v in regions.items()), key=lambda r: (-r["played"], r["name"])
    )
    return agg
