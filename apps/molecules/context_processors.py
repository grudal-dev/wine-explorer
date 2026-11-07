"""Signale une section Molécules vide (code à jour mais `load_seed` pas relancé)."""

from django.conf import settings
from django.db import DatabaseError


def data_status(request) -> dict:
    """`molecules_missing` vaut True si la section n'est pas chargée ou pas migrée.

    Affiché seulement en développement ou aux membres de l'équipe : en production, le
    conteneur relance `load_seed` à chaque démarrage.
    """
    user = getattr(request, "user", None)
    if not (settings.DEBUG or (user is not None and user.is_staff)):
        return {}
    from .models import Molecule, ProfileMolecule

    try:
        missing = not (Molecule.objects.exists() and ProfileMolecule.objects.exists())
        unmigrated = False
    except DatabaseError:
        missing, unmigrated = True, True
    return {"molecules_missing": missing, "molecules_unmigrated": unmigrated}
