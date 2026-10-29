"""Rattache au compte les parties jouées anonymement avant la connexion."""

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from apps.blindtest.models import Game
from apps.blindtest.views import SESSION_GAMES


@receiver(user_logged_in)
def claim_anonymous_games(sender, request, user, **kwargs):
    if request is None:
        return
    ids = request.session.get(SESSION_GAMES, [])
    if not ids:
        return
    has_daily = set(
        Game.objects.filter(user=user, mode=Game.Mode.DAILY).values_list("day", flat=True)
    )
    for game in Game.objects.filter(public_id__in=ids, user__isnull=True):
        if game.mode == Game.Mode.DAILY and game.day in has_daily:
            continue  # le compte a déjà son défi du jour
        game.user = user
        game.session_key = ""
        game.save(update_fields=["user", "session_key"])
        if game.mode == Game.Mode.DAILY:
            has_daily.add(game.day)
    request.session[SESSION_GAMES] = []
