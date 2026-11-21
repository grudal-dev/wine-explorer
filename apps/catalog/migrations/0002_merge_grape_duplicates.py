"""Fusionne les cépages déclarés deux fois : Rolle → Vermentino, Nielluccio → Sangiovese.

En production, `migrate` suffit : les vins de Provence et de Corse passent sur les fiches
Vermentino et Sangiovese, et les anciennes fiches disparaissent (leurs adresses redirigent).
"""

from django.db import migrations


def forwards(apps, schema_editor):
    from apps.catalog.grapes import apply_known_merges

    apply_known_merges(apps.get_model("catalog", "Grape"), apps.get_model("catalog", "ProfileGrape"))


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
