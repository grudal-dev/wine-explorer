import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.catalog.models import WineProfile


class Game(models.Model):
    class Mode(models.TextChoices):
        DAILY = "daily", "Défi du jour"
        FREE = "free", "Partie libre"

    class Status(models.TextChoices):
        PLAYING = "playing", "En cours"
        WON = "won", "Gagnée"
        LOST = "lost", "Perdue"
        ABANDONED = "abandoned", "Abandonnée"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE,
        related_name="games",
    )
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    profile = models.ForeignKey(WineProfile, on_delete=models.PROTECT, related_name="games")
    mode = models.CharField(max_length=8, choices=Mode.choices, default=Mode.FREE)
    day = models.DateField(null=True, blank=True, db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PLAYING)
    max_attempts = models.PositiveSmallIntegerField(default=8)
    clues_revealed = models.PositiveSmallIntegerField(default=0)
    found = models.JSONField(default=dict, blank=True)
    score = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "day"], condition=models.Q(mode="daily", user__isnull=False),
                name="one_daily_game_per_user",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_mode_display()} · {self.profile} · {self.get_status_display()}"

    def get_absolute_url(self):
        return reverse("blindtest:game", args=[self.public_id])

    @property
    def is_over(self) -> bool:
        return self.status != self.Status.PLAYING

    @property
    def attempts_used(self) -> int:
        return self.guesses.filter(counted=True).count()

    @property
    def attempts_left(self) -> int:
        return max(0, self.max_attempts - self.attempts_used)


class Guess(models.Model):
    class Verdict(models.TextChoices):
        HIT = "hit", "Trouvé"
        CLOSE = "close", "Proche"
        MISS = "miss", "Raté"
        INFO = "info", "Information"

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="guesses")
    raw = models.CharField(max_length=120)
    kind = models.CharField(max_length=16)
    value = models.CharField(max_length=40)
    label = models.CharField(max_length=160)
    verdict = models.CharField(max_length=8, choices=Verdict.choices)
    feedback = models.CharField(max_length=240)
    counted = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"{self.label} · {self.get_verdict_display()}"
