"""Molécules odorantes du vin et éléments naturels où on les retrouve.

Trois couches, chacune sourcée :

    WineProfile ──(ProfileMolecule)──▶ Molecule ──(Occurrence)──▶ NaturalSource

Le lien vin → molécule n'est pas saisi à la main pour chaque profil : il est
*déduit* au chargement par des règles documentées (un cépage, un style, une
couleur ou un descripteur du profil) et chaque lien garde la liste de ses
justifications, avec la référence bibliographique qui l'appuie. Le lien
molécule → élément naturel est, lui, une occurrence attestée par une source.
"""

from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from apps.catalog.models import Aroma, SluggedModel, WineProfile


class Reference(models.Model):
    """Une source : article, revue, ouvrage ou base de données."""

    key = models.SlugField("clé", max_length=60, unique=True)
    authors = models.CharField("auteurs", max_length=255)
    year = models.PositiveSmallIntegerField("année", null=True, blank=True)
    title = models.CharField("titre", max_length=400)
    container = models.CharField("revue ou éditeur", max_length=255, blank=True)
    doi = models.CharField(max_length=120, blank=True)
    url = models.URLField(max_length=400, blank=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["authors", "year"]
        verbose_name = "référence"

    def __str__(self) -> str:
        return self.short

    @property
    def short(self) -> str:
        first = self.authors.split(",")[0].split(" et ")[0].strip()
        many = "," in self.authors or " et " in self.authors
        return f"{first}{' et al.' if many else ''} {self.year or ''}".strip()

    @property
    def link(self) -> str:
        if self.doi:
            return f"https://doi.org/{self.doi}"
        return self.url


class ChemicalFamily(models.TextChoices):
    ESTER = "ester", "Ester"
    ALCOOL = "alcool", "Alcool"
    ALDEHYDE = "aldehyde", "Aldéhyde"
    CETONE = "cetone", "Cétone"
    TERPENE = "terpene", "Monoterpène"
    SESQUITERPENE = "sesquiterpene", "Sesquiterpène"
    NORISOPRENOIDE = "norisoprenoide", "Norisoprénoïde en C13"
    THIOL = "thiol", "Thiol"
    SULFURE = "sulfure", "Sulfure"
    PYRAZINE = "pyrazine", "Méthoxypyrazine"
    LACTONE = "lactone", "Lactone"
    FURANONE = "furanone", "Furanone"
    PHENOL = "phenol", "Phénol volatil"


class Origin(models.TextChoices):
    RAISIN = "raisin", "Raisin (arôme variétal)"
    PRECURSEUR = "precurseur", "Précurseur du raisin libéré par la levure"
    FERMENTATION = "fermentation", "Fermentation alcoolique"
    MALOLACTIQUE = "malolactique", "Fermentation malolactique"
    BOIS = "bois", "Élevage sous bois"
    VIEILLISSEMENT = "vieillissement", "Vieillissement et oxydation"
    ENVIRONNEMENT = "environnement", "Environnement de la vigne"


class Molecule(SluggedModel):
    name_en = models.CharField("nom anglais", max_length=160, help_text="Sert au lien PubChem.")
    synonyms = models.JSONField(default=list, blank=True)
    family = models.CharField("famille chimique", max_length=16, choices=ChemicalFamily.choices)
    origin = models.CharField("origine dans le vin", max_length=16, choices=Origin.choices)
    smiles = models.CharField(max_length=255)
    formula = models.CharField("formule brute", max_length=40, blank=True)
    molar_mass = models.FloatField("masse molaire (g/mol)", null=True, blank=True)
    odor = models.CharField("odeur", max_length=255)
    threshold = models.CharField("seuil de perception", max_length=160, blank=True)
    description = models.TextField(blank=True)
    aromas = models.ManyToManyField(
        Aroma, blank=True, related_name="molecules", verbose_name="descripteurs évoqués"
    )
    references = models.ManyToManyField(Reference, blank=True, related_name="molecules")
    universal = models.BooleanField(
        "socle commun", default=False,
        help_text="Présente dans pratiquement tous les vins (fermentation).",
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta(SluggedModel.Meta):
        ordering = ["order", "name"]
        verbose_name = "molécule"

    def get_absolute_url(self):
        return reverse("molecules:molecule", args=[self.slug])

    @property
    def display_name(self) -> str:
        """Majuscule initiale, sauf devant une lettre grecque (« β-ionone », pas « Β-ionone »)."""
        if self.name[:1] in GREEK:
            return self.name
        return self.name[:1].upper() + self.name[1:]

    @property
    def pubchem_url(self) -> str:
        from urllib.parse import quote

        return f"https://pubchem.ncbi.nlm.nih.gov/compound/{quote(self.name_en)}"

    @property
    def structure_static(self) -> str:
        return f"molecules/{self.slug}.svg"

    @property
    def formula_html(self) -> str:
        """C15H22O → C<sub>15</sub>H<sub>22</sub>O (échappé : la formule est contrôlée)."""
        import re

        from django.utils.html import escape

        return re.sub(r"(\d+)", r"<sub>\1</sub>", escape(self.formula))


class NaturalSource(SluggedModel):
    class Kind(models.TextChoices):
        EPICE = "epice", "Épice"
        HERBE = "herbe", "Herbe aromatique"
        FLEUR = "fleur", "Fleur"
        FRUIT = "fruit", "Fruit"
        LEGUME = "legume", "Légume"
        PLANTE = "plante", "Plante et feuillage"
        ARBRE = "arbre", "Arbre et bois"
        CHAMPIGNON = "champignon", "Champignon"
        ALIMENT = "aliment", "Aliment transformé"

    kind = models.CharField("nature", max_length=12, choices=Kind.choices)
    latin_name = models.CharField("nom scientifique", max_length=160, blank=True)
    description = models.TextField(blank=True)
    aroma = models.ForeignKey(
        Aroma, null=True, blank=True, on_delete=models.SET_NULL, related_name="natural_sources",
        help_text="Descripteur du vin portant le même nom, s'il existe.",
    )
    molecules = models.ManyToManyField(Molecule, through="Occurrence", related_name="sources")

    class Meta(SluggedModel.Meta):
        verbose_name = "élément naturel"
        verbose_name_plural = "éléments naturels"

    def get_absolute_url(self):
        return reverse("molecules:source", args=[self.slug])


class Occurrence(models.Model):
    """La molécule a été identifiée dans cet élément naturel."""

    molecule = models.ForeignKey(Molecule, on_delete=models.CASCADE, related_name="occurrences")
    source = models.ForeignKey(NaturalSource, on_delete=models.CASCADE, related_name="occurrences")
    note = models.CharField(max_length=255, blank=True)
    reference = models.ForeignKey(
        Reference, null=True, blank=True, on_delete=models.SET_NULL, related_name="occurrences"
    )

    class Meta:
        unique_together = [("molecule", "source")]
        ordering = ["source__name"]

    def __str__(self) -> str:
        return f"{self.molecule} ∈ {self.source}"


class Basis(models.TextChoices):
    """Pourquoi on rattache une molécule à un profil type."""

    GRAPE = "grape", "Marqueur du cépage"
    STYLE = "style", "Style de vinification"
    COLOR = "color", "Couleur du vin"
    AROMA = "aroma", "Descripteur du profil"
    UNIVERSAL = "universal", "Socle commun des vins"


BASIS_ORDER = [Basis.GRAPE, Basis.STYLE, Basis.COLOR, Basis.AROMA, Basis.UNIVERSAL]


class ProfileMolecule(models.Model):
    profile = models.ForeignKey(WineProfile, on_delete=models.CASCADE, related_name="profile_molecules")
    molecule = models.ForeignKey(Molecule, on_delete=models.CASCADE, related_name="profile_links")
    strength = models.PositiveSmallIntegerField(
        "force du lien", default=1, help_text="1 : plausible, 2 : probable, 3 : marqueur établi."
    )
    basis = models.CharField("justification principale", max_length=10, choices=Basis.choices)
    reasons = models.JSONField(
        "justifications", default=list,
        help_text="Liste de {basis, label, ref} produite par load_molecules.",
    )

    class Meta:
        unique_together = [("profile", "molecule")]
        ordering = ["-strength", "molecule__order", "molecule__name"]

    def __str__(self) -> str:
        return f"{self.profile} → {self.molecule} ({self.strength})"


GREEK = {"α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta"}


def slug_for(name: str) -> str:
    """Slug lisible pour un nom chimique : « β-damascénone » → « beta-damascenone »."""
    for letter, word in GREEK.items():
        name = name.replace(letter, word)
    return slugify(name.replace(",", "-"))
