"""Recalcule les liens vin → molécule : le sotolon et la MND ne suivent plus le style « vin doux
naturel » (un Porto Ruby n'en a pas de raison particulière) mais l'élevage oxydatif (règle « oxidative »
de molecules.yaml). Rien à lancer à la main : `migrate` rejoue `load_molecules`
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
        ("molecules", "0005_relink_oxidative"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
