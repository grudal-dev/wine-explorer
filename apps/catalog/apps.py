import os
import sys

from django.apps import AppConfig
from django.core import checks
from django.db import DatabaseError
from django.db.models.signals import post_migrate


def _autoload_enabled() -> bool:
    if os.environ.get("TERROIRS_AUTOLOAD", "true").lower() in {"0", "false", "no", "off"}:
        return False
    return "test" not in sys.argv[1:2]  # les tests chargent eux-mêmes leurs données


def load_missing_data(sender, verbosity=1, **kwargs):
    """Après `migrate` : charge les données de référence si la base est vide ou incomplète.

    Évite le piège d'une base migrée mais jamais (re)chargée, par exemple après un `git pull`
    qui ajoute la section Molécules : `migrate` suffit alors à tout remettre d'aplomb.
    """
    if not _autoload_enabled():
        return
    from django.core.management import call_command

    from apps.molecules.models import ProfileMolecule

    from .models import WineProfile

    out = sys.stdout if verbosity else open(os.devnull, "w")  # noqa: SIM115
    try:
        if not WineProfile.objects.exists():
            call_command("load_seed", stdout=out)
        elif not ProfileMolecule.objects.exists():
            call_command("load_molecules", stdout=out)
    except DatabaseError:
        pass  # migration partielle (une seule application) : rien à charger pour l'instant


def check_data_loaded(app_configs, **kwargs):
    """Avertit, au lancement de `runserver`, quand la base lue par le site est vide."""
    from apps.molecules.models import ProfileMolecule

    from .models import WineProfile

    if "test" in sys.argv[1:2]:
        return []  # la base de test est vide par construction
    try:
        if not WineProfile.objects.exists():
            return [checks.Warning(
                "Aucun vin en base : le site sera vide.",
                hint="Lancez `python manage.py migrate` (qui charge les données) ou `python manage.py load_seed`. "
                     "Vérifiez aussi DATABASE_URL dans .env : le serveur lit peut-être une autre base.",
                id="catalog.W001",
            )]
        if not ProfileMolecule.objects.exists():
            return [checks.Warning(
                "Aucune molécule associée aux vins : la section Molécules sera vide.",
                hint="Lancez `python manage.py load_seed` (ou `load_molecules`).",
                id="molecules.W001",
            )]
    except DatabaseError:
        return []  # tables absentes : `migrate` n'a pas encore tourné
    return []


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.catalog"
    verbose_name = "Catalogue"

    def ready(self):
        checks.register(check_data_loaded)
        post_migrate.connect(load_missing_data, sender=self)
