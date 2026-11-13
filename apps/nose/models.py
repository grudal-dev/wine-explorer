from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class HotColdResult(models.Model):
    """Résultat classé d'un joueur au chaud-froid du jour : un seul par joueur et par jour.

    Seules les parties du défi du jour, terminées par un joueur connecté, sont enregistrées ;
    les parties libres et les parties en cours restent dans la session (voir hotcold.py).
    """

    class Outcome(models.TextChoices):
        WON = "won", _("Trouvé")
        ABANDONED = "abandoned", _("Abandonné")

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="hotcold_results")
    day = models.DateField(db_index=True)
    secret = models.SlugField(max_length=120, help_text="Slug du profil de vin mystère ce jour-là")
    outcome = models.CharField(max_length=10, choices=Outcome.choices)
    guesses = models.PositiveSmallIntegerField()
    score = models.PositiveSmallIntegerField(default=0)
    finished_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "day"], name="hotcold_one_result_per_day")]
        ordering = ["day", "-score", "finished_at"]

    def __str__(self):
        return f"{self.user} {self.day} : {self.outcome} en {self.guesses}"
