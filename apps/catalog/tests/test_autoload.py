from io import StringIO
from unittest import mock

from django.apps import apps
from django.core.management import call_command
from django.test import TestCase

from apps.catalog.apps import check_data_loaded, load_missing_data
from apps.catalog.models import WineProfile
from apps.molecules.models import Molecule, ProfileMolecule


class AutoloadTests(TestCase):
    """`migrate` suffit à obtenir un site complet (cause du « aucune molécule associée aux vins »)."""

    def run_hook(self):
        with mock.patch("apps.catalog.apps._autoload_enabled", return_value=True):
            load_missing_data(sender=apps.get_app_config("catalog"), verbosity=0)

    def test_empty_database_gets_everything(self):
        self.assertFalse(WineProfile.objects.exists())
        self.run_hook()
        self.assertTrue(WineProfile.objects.exists())
        self.assertTrue(ProfileMolecule.objects.exists())

    def test_catalogue_without_molecules_is_completed(self):
        call_command("load_seed", "--skip-molecules", stdout=StringIO())
        self.assertFalse(Molecule.objects.exists())
        self.run_hook()
        self.assertGreater(ProfileMolecule.objects.count(), 300)
        self.assertFalse(WineProfile.objects.filter(profile_molecules__isnull=True).exists())

    def test_loaded_database_is_left_alone(self):
        call_command("load_seed", stdout=StringIO())
        with mock.patch("django.core.management.call_command") as cmd:
            self.run_hook()
        cmd.assert_not_called()

    def test_startup_warning(self):
        with mock.patch("sys.argv", ["manage.py", "runserver"]):
            self.assertEqual([w.id for w in check_data_loaded(None)], ["catalog.W001"])
            call_command("load_seed", "--skip-molecules", stdout=StringIO())
            self.assertEqual([w.id for w in check_data_loaded(None)], ["molecules.W001"])
            call_command("load_molecules", stdout=StringIO())
            self.assertEqual(check_data_loaded(None), [])
