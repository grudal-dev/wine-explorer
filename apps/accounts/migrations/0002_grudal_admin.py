"""Donne l'administration au compte « grudal » (demande du 18/11/2026).

Ne s'exécute qu'une fois, au déploiement : si le compte n'existe pas à ce moment-là, rien n'est fait, et un
compte créé plus tard sous ce nom ne deviendra jamais administrateur par ce biais.
"""

from django.db import migrations

USERNAME = "grudal"


def promote(apps, schema_editor):
    User = apps.get_model("auth", "User")
    User.objects.filter(username=USERNAME).update(is_staff=True, is_superuser=True)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [migrations.RunPython(promote, migrations.RunPython.noop)]
