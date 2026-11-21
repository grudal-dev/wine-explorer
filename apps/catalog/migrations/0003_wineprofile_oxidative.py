"""Élevage oxydatif : drapeau des vins longuement élevés au contact de l'air.

Les profils déjà en base sont marqués ici, pour que `migrate` suffise en production :
le style oxydatif (vin jaune, Szamorodni sec), le Porto Tawny 10 ans et le Porto Colheita.
"""

from django.db import migrations, models

OXIDATIVE_SLUGS = ["porto-tawny-10-ans", "porto-colheita"]


def forwards(apps, schema_editor):
    WineProfile = apps.get_model("catalog", "WineProfile")
    WineProfile.objects.filter(style="oxydatif").update(oxidative=True)
    WineProfile.objects.filter(slug__in=OXIDATIVE_SLUGS).update(oxidative=True)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0002_merge_grape_duplicates")]

    operations = [
        migrations.AddField(
            model_name="wineprofile",
            name="oxidative",
            field=models.BooleanField(
                default=False, verbose_name="élevage oxydatif",
                help_text="Long élevage au contact de l'air (tawny, vin jaune…) : les thiols et les acétates "
                          "de fermentation y ont disparu.",
            ),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
