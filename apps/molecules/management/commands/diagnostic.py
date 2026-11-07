"""Explique pourquoi un vin n'a pas de molécules, et propose la commande qui répare.

    python manage.py diagnostic            # constat seulement
    python manage.py diagnostic --reparer  # constat, puis migrate + load_seed si besoin

Affiche la base réellement utilisée (le piège le plus courant : `runserver` lit db.sqlite3
alors que Docker écrit dans PostgreSQL, ou l'inverse), les migrations en attente, le contenu
des tables et le résultat d'un chargement à blanc des fichiers de molécules.
"""

import subprocess
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection
from django.db.migrations.executor import MigrationExecutor


class Command(BaseCommand):
    help = "Diagnostique la section Molécules (base utilisée, migrations, données) et peut la réparer."

    def add_arguments(self, parser):
        parser.add_argument("--reparer", action="store_true", help="Lancer migrate puis load_seed si nécessaire.")

    def handle(self, *args, reparer=False, **options):
        problems = []
        out = self.stdout

        out.write(self.style.MIGRATE_HEADING("Code"))
        out.write(f"  dossier : {settings.BASE_DIR}")
        out.write(f"  commit  : {self._git_commit()}")
        has_cmd = (Path(__file__).parent / "load_molecules.py").exists()
        out.write(f"  section Molécules présente dans le code : {'oui' if has_cmd else 'NON'}")

        out.write(self.style.MIGRATE_HEADING("Base de données utilisée"))
        db = settings.DATABASES["default"]
        host = f"{db.get('HOST') or 'localhost'}:{db.get('PORT') or ''}"
        where = db["NAME"] if "sqlite" in db["ENGINE"] else f"{host}/{db['NAME']}"
        out.write(f"  moteur : {db['ENGINE'].rsplit('.', 1)[-1]}")
        out.write(f"  base   : {where}")

        out.write(self.style.MIGRATE_HEADING("Migrations"))
        try:
            executor = MigrationExecutor(connection)
            pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
        except DatabaseError as exc:
            raise CommandError(f"Base inaccessible : {exc}") from exc
        if pending:
            names = ", ".join(f"{m.app_label}.{m.name}" for m, _ in pending)
            out.write(self.style.WARNING(f"  {len(pending)} en attente : {names}"))
            problems.append("migrations")
        else:
            out.write("  à jour")

        out.write(self.style.MIGRATE_HEADING("Contenu"))
        counts = self._counts()
        for label, n in counts.items():
            line = f"  {label:<26} {n if n is not None else 'table absente'}"
            bad = n is None or (bool(n) if label == "vins sans molécule" else not n)
            out.write(self.style.WARNING(line) if bad else line)
        if not counts["profils (vins)"]:
            problems.append("catalogue")
        if not counts["molécules"] or not counts["liens vin → molécule"]:
            problems.append("molecules")
        elif counts["vins sans molécule"]:
            problems.append("orphelins")

        out.write(self.style.MIGRATE_HEADING("Fichiers de molécules (validation à blanc)"))
        if pending:
            out.write("  ignorée : appliquez d'abord les migrations")
        else:
            try:
                buf = StringIO()
                call_command("load_molecules", "--check", stdout=buf)
                out.write("  " + buf.getvalue().strip())
            except Exception as exc:  # noqa: BLE001 - on veut afficher toute erreur telle quelle
                out.write(self.style.ERROR(f"  ÉCHEC : {exc}"))
                problems.append("fichiers")

        out.write(self.style.MIGRATE_HEADING("Verdict"))
        if not problems:
            out.write(self.style.SUCCESS(
                "  Tout est chargé dans cette base. Si le site n'affiche rien, il lit une autre base : "
                "comparez la ligne « base » ci-dessus avec celle du serveur, puis redémarrez-le."
            ))
            return
        advice = {
            "migrations": "lancez `python manage.py migrate`.",
            "catalogue": "le catalogue est vide : lancez `python manage.py load_seed`.",
            "molecules": "les molécules ne sont pas chargées dans CETTE base : lancez `python manage.py load_seed`.",
            "orphelins": "des vins n'ont aucune molécule : relancez `python manage.py load_seed`.",
            "fichiers": "les fichiers de molécules sont invalides : envoyez l'erreur ci-dessus.",
        }
        for p in problems:
            out.write(self.style.WARNING(f"  - {advice[p]}"))

        if reparer and "fichiers" not in problems:
            out.write(self.style.MIGRATE_HEADING("Réparation"))
            call_command("migrate", interactive=False, verbosity=0)
            call_command("load_seed", stdout=self.stdout)
            after = self._counts()
            out.write(self.style.SUCCESS(
                f"  {after['molécules']} molécules, {after['liens vin → molécule']} liens, "
                f"{after['vins sans molécule']} vin(s) sans molécule. Redémarrez le serveur."
            ))
        elif not reparer:
            out.write("  Pour réparer automatiquement : python manage.py diagnostic --reparer")

    def _counts(self) -> dict:
        from apps.catalog.models import WineProfile
        from apps.molecules.models import Molecule, NaturalSource, ProfileMolecule

        def safe(fn):
            try:
                return fn()
            except DatabaseError:
                connection.close()
                return None

        return {
            "profils (vins)": safe(WineProfile.objects.count),
            "molécules": safe(Molecule.objects.count),
            "éléments naturels": safe(NaturalSource.objects.count),
            "liens vin → molécule": safe(ProfileMolecule.objects.count),
            "vins sans molécule": safe(
                lambda: WineProfile.objects.exclude(
                    pk__in=ProfileMolecule.objects.values("profile_id")
                ).count()
            ),
        }

    def _git_commit(self) -> str:
        try:
            res = subprocess.run(
                ["git", "log", "-1", "--format=%h %s (%cd)", "--date=short"],
                cwd=settings.BASE_DIR, capture_output=True, text=True, timeout=5, check=False,
            )
            return res.stdout.strip() or "inconnu (pas un dépôt git)"
        except (OSError, subprocess.SubprocessError):
            return "inconnu (git absent)"
