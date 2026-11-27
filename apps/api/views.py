"""API JSON des applications mobiles (/api/v1/).

Authentification par jeton (`Authorization: Token <clé>`). Sans compte, on joue quand même :
l'appareil s'identifie par `X-Device-Id`, et ses parties rejoignent le compte à la connexion.
La langue suit `Accept-Language` (fr, en).
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from apps.accounts import rankings
from apps.accounts.forms import SignupForm
from apps.blindtest import engine
from apps.blindtest.models import Game
from apps.blindtest.views import stats_for
from apps.catalog.i18n import tr, tr_list
from apps.catalog.models import Color, WineProfile
from apps.embeddings.space import space
from apps.explorer.graph import search_nodes
from apps.nose import hotcold

from .models import HotColdGame
from .owner import Owner, claim_device


class AuthThrottle(AnonRateThrottle):
    scope = "auth"  # connexion et inscription : limite les essais de mots de passe


def _error(message: str, code: int = status.HTTP_400_BAD_REQUEST, **extra) -> Response:
    return Response({"detail": str(message), **extra}, status=code)


def _need_player(owner: Owner):
    if not owner.known:
        return _error(gettext("Identifiant d'appareil manquant."), status.HTTP_400_BAD_REQUEST)
    return None


# ── Sérialisation ────────────────────────────────────────────────────────────
def _wine_brief(p: WineProfile) -> dict:
    return {"slug": p.slug, "name": tr(p.name), "color": p.color, "color_label": p.get_color_display()}


def _game_json(game: Game, owner: Owner) -> dict:
    sheet = engine.tasting_sheet(game)
    out = {
        "id": str(game.public_id), "mode": game.mode, "mode_label": game.get_mode_display(),
        "day": game.day, "status": game.status, "status_label": game.get_status_display(),
        "is_over": game.is_over, "is_owner": owner.owns(game), "score": game.score,
        "attempts_used": game.attempts_used, "attempts_left": game.attempts_left,
        "max_attempts": game.max_attempts,
        "player": game.user.username if game.user_id else None,
        "sheet": {
            "color": sheet["color_key"], "color_label": str(sheet["color"]), "style": str(sheet["style"]),
            "structure": [{"label": str(label), "value": value} for label, value in sheet["structure"]],
            "aromas": sheet["aromas"], "aromas_hidden": sheet["aromas_hidden"],
            "clues": [{"key": c["key"], "title": str(c["title"]), "body": c["body"]} for c in sheet["clues"]],
            "next_clue": str(sheet["next_clue"]) if sheet["next_clue"] else None,
            "slots": [{"key": s["key"], "label": s["label"], "found": s["found"],
                       "answer": s["answer"] if s["show"] else None} for s in sheet["slots"]],
            "minor_grapes": sheet["minor_grapes"],
        },
        "guesses": [{"label": tr(g.label), "kind": g.kind, "verdict": g.verdict,
                     "verdict_label": g.get_verdict_display(), "feedback": g.feedback, "counted": g.counted}
                    for g in game.guesses.all()],
        "wine": _wine_brief(game.profile) if game.is_over else None,
    }
    return out


def _game_row(game: Game) -> dict:
    return {"id": str(game.public_id), "mode": game.mode, "mode_label": game.get_mode_display(),
            "status": game.status, "status_label": game.get_status_display(), "score": game.score,
            "created_at": game.created_at, "wine": _wine_brief(game.profile) if game.is_over else None}


def _hotcold_rows(rows) -> list[dict]:
    return [{"day": r.day, "outcome": r.outcome, "outcome_label": r.get_outcome_display(),
             "guesses": r.guesses, "score": r.score, "wine": _wine_brief(r.wine) if r.wine else None}
            for r in rows]


def _stats(user) -> dict:
    s = stats_for(user)
    return {"played": s["played"], "won": s["won"], "rate": s["rate"], "avg": round(s["avg"] or 0),
            "regions": [{**r, "name": tr(r["name"])} for r in s["regions"]]}


def _user_json(user) -> dict:
    return {"username": user.username, "email": user.email, "date_joined": user.date_joined}


# ── Compte ───────────────────────────────────────────────────────────────────
def _session(user, request, code=status.HTTP_200_OK) -> Response:
    claim_device(user, request.headers.get("X-Device-Id", ""))
    token, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token.key, "user": _user_json(user)}, status=code)


@api_view(["POST"])
@throttle_classes([AuthThrottle])
def signup(request):
    data = request.data
    form = SignupForm({
        "username": data.get("username", ""), "email": data.get("email", ""),
        "password": data.get("password", ""),
        "adult": bool(data.get("adult")), "newsletter": bool(data.get("newsletter")),
    })
    if not form.is_valid():
        errors = {("password" if k.startswith("password") else k): [str(m) for m in v]
                  for k, v in form.errors.items()}
        return _error(gettext("Vérifiez les champs du formulaire."), errors=errors)
    return _session(form.save(), request, status.HTTP_201_CREATED)



@api_view(["POST"])
@throttle_classes([AuthThrottle])
def login(request):
    ident = str(request.data.get("username", "")).strip()
    password = str(request.data.get("password", ""))
    if "@" in ident:  # connexion par e-mail acceptée
        found = User.objects.filter(email__iexact=ident).first()
        ident = found.username if found else ident
    user = authenticate(request, username=ident, password=password)
    if user is None:
        return _error(gettext("Identifiant ou mot de passe incorrect."), status.HTTP_401_UNAUTHORIZED)
    return _session(user, request)



@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    Token.objects.filter(user=request.user).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET", "DELETE"])
@permission_classes([IsAuthenticated])
def me(request):
    user = request.user
    if request.method == "DELETE":
        # Suppression du compte depuis l'appli (exigée par l'App Store et Google Play).
        if not user.check_password(str(request.data.get("password", ""))):
            return _error(gettext("Mot de passe incorrect."), status.HTTP_403_FORBIDDEN)
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    return Response({
        "user": _user_json(user), "stats": _stats(user),
        "games": [_game_row(g) for g in user.games.select_related("profile")[:30]],
        "hotcold": _hotcold_rows(hotcold.history(user)),
    })


# ── Accueil : les deux défis du jour ─────────────────────────────────────────
@api_view(["GET"])
def today(request):
    owner = Owner.of(request)
    now = timezone.localtime()
    tomorrow = timezone.make_aware(datetime.combine(now.date() + timedelta(days=1), time.min))
    day = now.date()

    bt = owner.games().filter(mode=Game.Mode.DAILY, day=day).first()
    blind = {"state": "todo", "game_id": None, "score": None, "status_label": None}
    if bt:
        blind = {"state": "done" if bt.is_over else "playing", "game_id": str(bt.public_id),
                 "score": bt.score if bt.is_over else None,
                 "status_label": bt.get_status_display()}

    hc = owner.hotcold_games().filter(mode="daily", day=day).first()
    hot = {"state": "todo", "guesses": 0, "score": None}
    if owner.hotcold_done(day) or (hc and hc.over):
        won = bool(hc and hc.over == "won")
        guesses = len(hc.guesses) if hc else 0
        if owner.user:
            r = owner.user.hotcold_results.filter(day=day).first()
            if r:
                won, guesses = r.outcome == "won", r.guesses
        hot = {"state": "done", "guesses": guesses, "score": hotcold.points(guesses, won)}
    elif hc and hc.guesses:
        hot = {"state": "playing", "guesses": len(hc.guesses), "score": None}

    return Response({"day": day, "seconds_left": int((tomorrow - now).total_seconds()),
                     "blindtest": blind, "hotcold": hot,
                     "colors": [{"key": k, "label": str(v)} for k, v in Color.choices]})


# ── Blind test ───────────────────────────────────────────────────────────────
@api_view(["GET", "POST"])
def blindtest_games(request):
    owner = Owner.of(request)
    if (err := _need_player(owner)) is not None:
        return err
    if request.method == "GET":
        return Response({"results": [_game_row(g) for g in owner.games().select_related("profile")[:30]]})
    mode = Game.Mode.DAILY if request.data.get("mode") == "daily" else Game.Mode.FREE
    color = request.data.get("color", "")
    color = color if color in Color.values else ""
    game = engine.new_game(mode=mode, user=owner.user, session_key=owner.device,
                           session_games=list(owner.games().values_list("public_id", flat=True)),
                           color=color)
    return Response(_game_json(game, owner), status=status.HTTP_201_CREATED)


def _visible_game(request, public_id) -> tuple[Game, Owner]:
    owner = Owner.of(request)
    game = get_object_or_404(Game.objects.select_related("profile__appellation__region__parent", "user"),
                             public_id=public_id)
    if not owner.owns(game):
        # La partie d'un autre : seulement terminée, et jamais sur le vin du jour avant d'avoir fini le sien.
        from django.http import Http404
        if not game.is_over or game.profile_id == owner.blindtest_spoiler(timezone.localdate()):
            raise Http404
    return game, owner


@api_view(["GET"])
def blindtest_game(request, public_id):
    game, owner = _visible_game(request, public_id)
    return Response(_game_json(game, owner))


@api_view(["POST"])
def blindtest_guess(request, public_id):
    game, owner = _visible_game(request, public_id)
    if not owner.owns(game):
        return _error(gettext("Ce n'est pas votre partie."), status.HTTP_403_FORBIDDEN)
    try:
        engine.play(game, str(request.data.get("q", "")), str(request.data.get("choice", "")))
    except engine.GuessError as exc:
        return _error(str(exc))
    game.refresh_from_db()
    return Response(_game_json(game, owner))


@api_view(["POST"])
def blindtest_give_up(request, public_id):
    game, owner = _visible_game(request, public_id)
    if not owner.owns(game):
        return _error(gettext("Ce n'est pas votre partie."), status.HTTP_403_FORBIDDEN)
    engine.abandon(game)
    game.refresh_from_db()
    return Response(_game_json(game, owner))


@api_view(["GET"])
def blindtest_suggest(request):
    return Response({"results": engine.suggest(str(request.query_params.get("q", ""))[:80])})


# ── Chaud-froid ──────────────────────────────────────────────────────────────
def _hotcold_current(owner: Owner, sp) -> HotColdGame:
    today = timezone.localdate()
    game = owner.hotcold_games().first()
    stale = (game is None or f"profile:{game.secret}" not in sp
             or (game.mode == "daily" and game.day != today))
    if stale:
        game = _hotcold_new(owner, sp, "daily")
    return game


def _hotcold_new(owner: Owner, sp, mode: str, exclude: str = "") -> HotColdGame:
    today = timezone.localdate()
    if mode == "daily":
        existing = owner.hotcold_games().filter(mode="daily", day=today).first()
        if existing:
            existing.save(update_fields=["updated_at"])  # redevient la partie courante
            return existing
    state = hotcold.new_state(mode, today, sp, exclude=exclude)
    return HotColdGame.objects.create(user=owner.user, device=owner.device, mode=mode, day=today,
                                      secret=state["secret"])


def _hotcold_json(game: HotColdGame, sp, owner: Owner) -> dict:
    board = hotcold.board(game.state, sp)
    ranked = None
    if owner.user and game.mode == "daily" and game.over:
        r = hotcold.record_result(owner.user, game.state)
        ranked = {"score": r.score, "guesses": r.guesses} if r else None
    return {"mode": game.mode, "day": game.day, "ranked": ranked, **board}


def _space_or_error():
    sp = space()
    if sp is None:
        return None, _error(gettext("Le chaud-froid n'est pas disponible."), status.HTTP_503_SERVICE_UNAVAILABLE)
    return sp, None


@api_view(["GET"])
def hotcold_current(request):
    owner = Owner.of(request)
    if (err := _need_player(owner)) is not None:
        return err
    sp, err = _space_or_error()
    if err:
        return err
    try:
        game = _hotcold_current(owner, sp)
    except hotcold.HotColdError as exc:
        return _error(str(exc), status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response(_hotcold_json(game, sp, owner))


@api_view(["POST"])
def hotcold_new(request):
    owner = Owner.of(request)
    if (err := _need_player(owner)) is not None:
        return err
    sp, err = _space_or_error()
    if err:
        return err
    mode = "daily" if request.data.get("mode") == "daily" else "free"
    previous = owner.hotcold_games().first()
    try:
        game = _hotcold_new(owner, sp, mode, exclude=previous.secret if previous else "")
    except hotcold.HotColdError as exc:
        return _error(str(exc), status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response(_hotcold_json(game, sp, owner), status=status.HTTP_201_CREATED)


@api_view(["POST"])
def hotcold_guess(request):
    owner = Owner.of(request)
    if (err := _need_player(owner)) is not None:
        return err
    sp, err = _space_or_error()
    if err:
        return err
    game = _hotcold_current(owner, sp)
    state = game.state
    try:
        hotcold.play(state, str(request.data.get("q", "")), str(request.data.get("choice", "")), sp)
    except hotcold.HotColdError as exc:
        return _error(str(exc))
    game.apply(state)
    return Response(_hotcold_json(game, sp, owner))


@api_view(["POST"])
def hotcold_give_up(request):
    owner = Owner.of(request)
    if (err := _need_player(owner)) is not None:
        return err
    sp, err = _space_or_error()
    if err:
        return err
    game = _hotcold_current(owner, sp)
    if not game.over:
        state = game.state
        state["over"] = "abandoned"
        game.apply(state)
    return Response(_hotcold_json(game, sp, owner))


@api_view(["GET"])
def hotcold_suggest(request):
    sp = space()
    q = str(request.query_params.get("q", ""))[:80]
    if sp is None or not q.strip():
        return Response({"results": []})
    hits = [h for h in search_nodes(q, limit=20) if h["id"] in sp][:8]
    return Response({"results": [{"id": h["id"], "label": h["label"], "type": h["type"],
                                  "type_label": str(h["type_label"])} for h in hits]})


# ── Classements et joueurs ───────────────────────────────────────────────────
@api_view(["GET"])
def ranking(request):
    game = request.query_params.get("game", "total")
    game = game if game in rankings.GAMES else "total"
    data = rankings.standings(game, timezone.localdate())
    return Response({"game": game, "day": timezone.localdate(), **data})


@api_view(["GET"])
def player(request, username):
    owner_user = get_object_or_404(User, username=username)
    viewer = Owner.of(request)
    today = timezone.localdate()
    is_self = viewer.user is not None and viewer.user.id == owner_user.id
    games = owner_user.games.exclude(status=Game.Status.PLAYING).select_related("profile")
    hide_today = None
    if not is_self:
        games = games.exclude(profile_id=viewer.blindtest_spoiler(today))
        hide_today = None if viewer.hotcold_done(today) else today
    return Response({
        "username": owner_user.username, "is_self": is_self, "stats": _stats(owner_user),
        "games": [_game_row(g) for g in games[:30]],
        "hotcold": _hotcold_rows(hotcold.history(owner_user, hide_today=hide_today)),
    })


# ── Fiche vin ────────────────────────────────────────────────────────────────
@api_view(["GET"])
def wine(request, slug):
    p = get_object_or_404(WineProfile.objects.select_related("appellation__region__parent"), slug=slug)
    region = p.appellation.region
    return Response({
        **_wine_brief(p), "style": p.get_style_display(),
        "appellation": p.appellation.name,
        "region": tr(region.root.name), "subregion": tr(region.name) if region.parent_id else None,
        "grapes": [{"name": pg.grape.name, "share": pg.share}
                   for pg in p.profile_grapes.select_related("grape")],
        "aromas": [{"name": tr(pa.aroma.name), "family": tr(pa.aroma.family.name), "hue": pa.aroma.family.color,
                    "intensity": pa.intensity} for pa in p.profile_aromas.select_related("aroma__family")],
        "structure": [{"label": str(label), "value": value} for label, value in p.structure],
        "description": tr(p.description), "pairings": tr_list(p.pairings),
        "price_min": p.price_min, "price_max": p.price_max,
        "aging_min": p.aging_min, "aging_max": p.aging_max, "serving_temp": tr(p.serving_temp),
    })


@api_view(["GET"])
def wines(request):
    q = str(request.query_params.get("q", "")).strip()[:60]
    qs = WineProfile.objects.select_related("appellation").order_by("name")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(appellation__name__icontains=q))
    return Response({"results": [_wine_brief(p) for p in qs[:40]]})
