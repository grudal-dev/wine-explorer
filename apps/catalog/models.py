"""Modèle de données du monde du vin.

Le schéma est pensé « monde » dès le départ : un pays porte des régions
(hiérarchiques), qui portent des appellations, quelle que soit la
classification locale (AOC, IGP, DOC, DOCG, AVA…). Le *profil type*
(WineProfile) est l'unité jouable : une appellation, une couleur, un style,
un encépagement typique, des arômes pondérés et une structure en bouche.
"""

from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class SluggedModel(models.Model):
    name = models.CharField("nom", max_length=160)
    slug = models.SlugField(max_length=180, unique=True)

    class Meta:
        abstract = True
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Country(SluggedModel):
    code = models.CharField("code ISO", max_length=2, unique=True)

    class Meta(SluggedModel.Meta):
        verbose_name = "pays"
        verbose_name_plural = "pays"


class Region(SluggedModel):
    class Kind(models.TextChoices):
        REGION = "region", "Région viticole"
        SUBREGION = "subregion", "Sous-région"

    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name="regions")
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.REGION)
    description = models.TextField(blank=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)

    class Meta(SluggedModel.Meta):
        verbose_name = "région"

    def get_absolute_url(self):
        return reverse("catalog:region", args=[self.slug])

    @property
    def root(self) -> "Region":
        return self.parent.root if self.parent_id else self

    def lineage(self) -> list["Region"]:
        return (self.parent.lineage() if self.parent_id else []) + [self]


class Color(models.TextChoices):
    ROUGE = "rouge", "Rouge"
    BLANC = "blanc", "Blanc"
    ROSE = "rose", "Rosé"


class Style(models.TextChoices):
    TRANQUILLE = "tranquille", "Tranquille sec"
    EFFERVESCENT = "effervescent", "Effervescent"
    MOELLEUX = "moelleux", "Moelleux"
    LIQUOREUX = "liquoreux", "Liquoreux"
    MUTE = "mute", "Vin doux naturel"
    OXYDATIF = "oxydatif", "Vin jaune (oxydatif)"


class Appellation(SluggedModel):
    class Classification(models.TextChoices):
        AOC = "AOC", "AOC / AOP"
        IGP = "IGP", "IGP"
        DOC = "DOC", "DOC"
        DOCG = "DOCG", "DOCG"
        AVA = "AVA", "AVA"
        OTHER = "OTHER", "Autre"

    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name="appellations")
    region = models.ForeignKey(Region, on_delete=models.PROTECT, related_name="appellations")
    classification = models.CharField(
        max_length=8, choices=Classification.choices, default=Classification.AOC
    )
    colors = models.JSONField("couleurs autorisées", default=list, blank=True)
    lat = models.FloatField(null=True, blank=True, help_text="Position approximative (commune centrale).")
    lng = models.FloatField(null=True, blank=True)
    inao_code = models.CharField("identifiant INAO", max_length=32, blank=True)
    wikidata_id = models.CharField(max_length=20, blank=True)
    communes_count = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    source = models.CharField(max_length=120, default="seed:terroirs")

    class Meta(SluggedModel.Meta):
        verbose_name = "appellation"

    def get_absolute_url(self):
        return reverse("catalog:appellation", args=[self.slug])


class Grape(SluggedModel):
    class Skin(models.TextChoices):
        NOIR = "noir", "Noir"
        BLANC = "blanc", "Blanc"
        GRIS = "gris", "Gris / rosé"

    skin = models.CharField("couleur de baie", max_length=8, choices=Skin.choices)
    synonyms = models.JSONField(default=list, blank=True)
    origin = models.CharField("berceau", max_length=120, blank=True)
    description = models.TextField(blank=True)
    wikidata_id = models.CharField(max_length=20, blank=True)

    class Meta(SluggedModel.Meta):
        verbose_name = "cépage"

    def get_absolute_url(self):
        return reverse("catalog:grape", args=[self.slug])


class AromaFamily(SluggedModel):
    order = models.PositiveSmallIntegerField(default=0)
    color = models.CharField(max_length=7, default="#888888")

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "famille aromatique"
        verbose_name_plural = "familles aromatiques"


class Aroma(SluggedModel):
    family = models.ForeignKey(AromaFamily, on_delete=models.PROTECT, related_name="aromas")
    synonyms = models.JSONField(default=list, blank=True)

    class Meta(SluggedModel.Meta):
        verbose_name = "arôme"

    def get_absolute_url(self):
        return reverse("catalog:aroma", args=[self.slug])


class WineProfile(SluggedModel):
    """Un vin « type » : ce que l'on attend d'une appellation dans une couleur et un style."""

    appellation = models.ForeignKey(Appellation, on_delete=models.CASCADE, related_name="profiles")
    color = models.CharField("couleur", max_length=8, choices=Color.choices)
    style = models.CharField(max_length=14, choices=Style.choices, default=Style.TRANQUILLE)
    grapes = models.ManyToManyField(Grape, through="ProfileGrape", related_name="profiles")
    aromas = models.ManyToManyField(Aroma, through="ProfileAroma", related_name="profiles")

    body = models.PositiveSmallIntegerField("corps", default=3)
    acidity = models.PositiveSmallIntegerField("acidité", default=3)
    tannin = models.PositiveSmallIntegerField("tanins", default=0)
    sweetness = models.PositiveSmallIntegerField("sucrosité", default=1)

    price_min = models.PositiveIntegerField("prix min (€)", null=True, blank=True)
    price_max = models.PositiveIntegerField("prix max (€)", null=True, blank=True)
    aging_min = models.PositiveSmallIntegerField("garde min (ans)", null=True, blank=True)
    aging_max = models.PositiveSmallIntegerField("garde max (ans)", null=True, blank=True)
    serving_temp = models.CharField("service", max_length=40, blank=True)
    pairings = models.JSONField("accords", default=list, blank=True)
    description = models.TextField(blank=True)

    class Meta(SluggedModel.Meta):
        verbose_name = "profil type"
        verbose_name_plural = "profils types"

    def get_absolute_url(self):
        return reverse("catalog:profile", args=[self.slug])

    @property
    def region(self) -> Region:
        return self.appellation.region

    @property
    def structure(self) -> list[tuple[str, int]]:
        return [
            ("Corps", self.body), ("Acidité", self.acidity),
            ("Tanins", self.tannin), ("Sucrosité", self.sweetness),
        ]

    def main_grapes(self, threshold: int = 20):
        return [pg.grape for pg in self.profile_grapes.all() if pg.share >= threshold]


class ProfileGrape(models.Model):
    profile = models.ForeignKey(WineProfile, on_delete=models.CASCADE, related_name="profile_grapes")
    grape = models.ForeignKey(Grape, on_delete=models.CASCADE, related_name="profile_links")
    share = models.PositiveSmallIntegerField("part typique (%)", default=100)

    class Meta:
        ordering = ["-share"]
        unique_together = [("profile", "grape")]

    def __str__(self) -> str:
        return f"{self.grape} {self.share} %"


class ProfileAroma(models.Model):
    class Intensity(models.IntegerChoices):
        DISCRET = 1, "Discret"
        PRESENT = 2, "Présent"
        DOMINANT = 3, "Dominant"

    profile = models.ForeignKey(WineProfile, on_delete=models.CASCADE, related_name="profile_aromas")
    aroma = models.ForeignKey(Aroma, on_delete=models.CASCADE, related_name="profile_links")
    intensity = models.PositiveSmallIntegerField(choices=Intensity.choices, default=2)

    class Meta:
        ordering = ["-intensity", "aroma__name"]
        unique_together = [("profile", "aroma")]

    def __str__(self) -> str:
        return f"{self.aroma} ({self.intensity})"
