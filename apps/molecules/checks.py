"""Avertit dès `runserver` quand la base n'a pas de molécules (code à jour, données non rechargées)."""

import sys

from django.core.checks import Warning, register
from django.db import DatabaseError


@register()
def molecules_loaded(app_configs=None, **kwargs):
    # Seulement au lancement du serveur : inutile (et trompeur) pendant migrate ou load_seed.
    if "runserver" not in sys.argv:
        return []
    from .models import Molecule, ProfileMolecule

    try:
        empty = not (Molecule.objects.exists() and ProfileMolecule.objects.exists())
    except DatabaseError:
        return []  # migrations pas encore appliquées : Django le signale déjà
    if not empty:
        return []
    return [Warning(
        "La section Molécules est vide dans cette base : aucun vin n'a de molécule.",
        hint="Lancez `python manage.py load_seed` (ou `python manage.py diagnostic`).",
        id="molecules.W001",
    )]
