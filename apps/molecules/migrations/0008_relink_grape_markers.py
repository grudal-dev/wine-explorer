"""Recalcule les liens vin → molécule : l'oxyde de rose cis, le géraniol, le citronellol et le nérol
deviennent des marqueurs de cépage (clé aroma_needs_rule) ; le descripteur « rose » seul ne les relie
plus à un Barolo. `migrate` rejoue `load_molecules` sur une base déjà remplie.
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
        ("molecules", "0007_relink_audit"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
