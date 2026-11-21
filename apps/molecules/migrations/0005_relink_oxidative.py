"""Recalcule les liens vin → molécule après l'ajout de l'élevage oxydatif.

Les thiols variétaux et l'acétate d'isoamyle ne sont plus reliés aux vins à élevage oxydatif
(règle « fades » de molecules.yaml). Rien à lancer à la main : `migrate` rejoue `load_molecules`
sur une base déjà remplie ; une base vide est chargée plus tard par le signal post_migrate.
"""

import io

from django.core.management import call_command
from django.db import migrations


def forwards(apps, schema_editor):
    if not apps.get_model("molecules", "ProfileMolecule").objects.exists():
        return
    call_command("load_molecules", stdout=io.StringIO())


class Migration(migrations.Migration):
    dependencies = [
        ("molecules", "0004_molecule_attack"),
        ("catalog", "0003_wineprofile_oxidative"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
