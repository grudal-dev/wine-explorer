"""Qui joue : un compte (jeton) ou, sans compte, un appareil (en-tête X-Device-Id).

Les règles anti-spoiler du site sont reprises ici : le vin du jour d'un défi n'apparaît nulle part
(parties, historiques) tant que le joueur n'a pas terminé ce défi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from django.db.models import QuerySet

from apps.blindtest import engine
from apps.blindtest.models import Game
from apps.nose import hotcold
from apps.nose.models import HotColdResult

from .models import HotColdGame

DEVICE_RE = re.compile(r"^[A-Za-z0-9-]{8,36}$")


@dataclass
class Owner:
    user: object | None
    device: str  # "" si absent ou si le joueur est connecté

    @classmethod
    def of(cls, request) -> Owner:
        user = request.user if request.user.is_authenticated else None
        raw = request.headers.get("X-Device-Id", "").strip()
        device = "d-" + raw.replace("-", "")[:32] if DEVICE_RE.match(raw) else ""
        return cls(user=user, device="" if user else device)

    @property
    def known(self) -> bool:
        return bool(self.user or self.device)

    # ── Blind test ──
    def games(self) -> QuerySet[Game]:
        if self.user:
            return Game.objects.filter(user=self.user)
        if self.device:
            return Game.objects.filter(user__isnull=True, session_key=self.device)
        return Game.objects.none()

    def owns(self, game: Game) -> bool:
        if game.user_id:
            return bool(self.user) and game.user_id == self.user.id
        return bool(self.device) and game.session_key == self.device

    def blindtest_done(self, today: date) -> bool:
        return (self.games().filter(mode=Game.Mode.DAILY, day=today)
                .exclude(status=Game.Status.PLAYING).exists())

    def blindtest_spoiler(self, today: date) -> int | None:
        """Le vin du blind test du jour, tant que ce joueur n'a pas fini son défi ; sinon None."""
        return None if self.blindtest_done(today) else engine.daily_profile(today).id

    # ── Chaud-froid ──
    def hotcold_games(self) -> QuerySet[HotColdGame]:
        if self.user:
            return HotColdGame.objects.filter(user=self.user)
        if self.device:
            return HotColdGame.objects.filter(user__isnull=True, device=self.device)
        return HotColdGame.objects.none()

    def hotcold_done(self, today: date) -> bool:
        if self.user and HotColdResult.objects.filter(user=self.user, day=today).exists():
            return True
        return self.hotcold_games().filter(mode="daily", day=today).exclude(over="").exists()


def claim_device(user, raw_device: str) -> None:
    """À la connexion : rattache au compte les parties jouées sur l'appareil sans compte."""
    if not DEVICE_RE.match(raw_device or ""):
        return
    device = "d-" + raw_device.replace("-", "")[:32]
    has_daily = set(Game.objects.filter(user=user, mode=Game.Mode.DAILY).values_list("day", flat=True))
    for game in Game.objects.filter(user__isnull=True, session_key=device):
        if game.mode == Game.Mode.DAILY and game.day in has_daily:
            continue  # le compte a déjà son défi de ce jour-là
        game.user, game.session_key = user, ""
        game.save(update_fields=["user", "session_key"])
        if game.mode == Game.Mode.DAILY:
            has_daily.add(game.day)
    for hc in HotColdGame.objects.filter(user__isnull=True, device=device):
        hc.user, hc.device = user, ""
        hc.save(update_fields=["user", "device", "updated_at"])
        if hc.mode == "daily" and hc.over:
            hotcold.record_result(user, hc.state)  # idempotent : le premier résultat du jour compte
