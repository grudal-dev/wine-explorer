"""Recalcule les liens vin → molécule après l'audit du 25/11/2026 :

- plus de repli par famille d'arômes (eugénol relié à la « réglisse », 3-sulfanylhexanol au « citron »…) ;
- les conditions d'une règle se cumulent : cépage ET couleur / style (plus de bouquet de vieux bordeaux
  rouge dans un rosé moelleux, plus de cinnamate de Pinot noir rouge dans un Champagne) ;
- molécules de défaut (Brettanomyces) jamais rattachées à un profil ; benzaldéhyde sans « cerise ».

Rien à lancer à la main : `migrate` rejoue `load_molecules` sur une base déjà remplie.
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
        ("molecules", "0006_relink_sotolon"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
