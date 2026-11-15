"""Parties de chaud-froid des applications mobiles.

Sur le site, la partie en cours vit dans la session du navigateur. Une application n'a pas de
session : la partie est gardée ici, rattachée au compte ou, sans compte, à l'identifiant
d'appareil (en-tête `X-Device-Id`). Le vin mystère reste côté serveur jusqu'à la fin.
"""

from django.conf import settings
from django.db import models


class HotColdGame(models.Model):
    class Mode(models.TextChoices):
        DAILY = "daily", "Défi du jour"
        FREE = "free", "Partie libre"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE,
                             related_name="hotcold_games")
    device = models.CharField(max_length=40, blank=True, db_index=True)
    mode = models.CharField(max_length=8, choices=Mode.choices)
    day = models.DateField()
    secret = models.SlugField(max_length=120)
    guesses = models.JSONField(default=list, blank=True)
    over = models.CharField(max_length=10, blank=True)  # "", "won", "abandoned"
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        verbose_name = "partie de chaud-froid (appli)"
        verbose_name_plural = "parties de chaud-froid (appli)"

    def __str__(self):
        return f"{self.user or self.device} {self.mode} {self.day}"

    @property
    def state(self) -> dict:
        """La partie sous la forme qu'attend apps.nose.hotcold."""
        return {"mode": self.mode, "day": self.day.isoformat(), "secret": self.secret,
                "guesses": list(self.guesses), "over": self.over}

    def apply(self, state: dict) -> None:
        self.guesses, self.over = state["guesses"], state["over"]
        self.save(update_fields=["guesses", "over", "updated_at"])
