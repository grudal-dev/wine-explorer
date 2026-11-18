"""Donne l'administration au compte « GRUDAL » (demande du 18/11/2026).

La migration 0002 cherchait « grudal » en minuscules exactes ; le compte peut avoir été créé avec des majuscules.
Même règle : ne s'exécute qu'une fois, au déploiement.
"""

from django.db import migrations

USERNAMES = ("grudal", "GRUDAL")


def promote(apps, schema_editor):
    User = apps.get_model("auth", "User")
    User.objects.filter(username__in=USERNAMES).update(is_staff=True, is_superuser=True)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_grudal_admin")]

    operations = [migrations.RunPython(promote, migrations.RunPython.noop)]
