"""Met à jour et compile les catalogues de traduction, sans GNU gettext.

    python manage.py translations             # extrait, fusionne, compile, signale les manques
    python manage.py translations --check     # échoue s'il manque une traduction (pour les tests)
    python manage.py translations --missing   # liste les chaînes non traduites

Commande de développement : elle demande Babel (`pip install babel`), qui n'est pas une
dépendance du site. Les fichiers .mo compilés sont versionnés : le site n'a besoin de rien.

Deux catalogues par langue, dans locale/<langue>/LC_MESSAGES/ :
  django.po    interface (gabarits, code Python) et contenu de la base (arômes, descriptions…)
  djangojs.po  messages des scripts (static/js)

Le texte français sert d'identifiant. Pour corriger une traduction : modifier le msgstr dans
le .po, puis relancer cette commande.
"""

import io
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import templatize

KEYWORDS = {
    "_": None, "gettext": None, "gettext_lazy": None, "gettext_noop": None,
    "ngettext": (1, 2), "ngettext_lazy": (1, 2), "pgettext": ((1, "c"), 2),
}
HAS_LETTERS = re.compile(r"[^\W\d_]{2,}")
TEMPLATE_CALL = re.compile(r"""\bgettext\(u?('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")\)""")


class Command(BaseCommand):
    help = "Extrait les chaînes à traduire, fusionne les catalogues .po et compile les .mo."

    def add_arguments(self, parser):
        parser.add_argument("--check", action="store_true", help="Échouer s'il manque une traduction.")
        parser.add_argument("--missing", action="store_true", help="Lister les chaînes non traduites.")

    def handle(self, *args, check, missing, **options):
        try:
            from babel.messages import mofile, pofile
            from babel.messages.catalog import Catalog
        except ImportError as exc:
            raise CommandError("Babel est requis : pip install babel") from exc

        base = Path(settings.BASE_DIR)
        found = {"django": self._interface(base) | self._data(), "djangojs": self._scripts(base)}
        todo = 0
        for code, _name in settings.LANGUAGES:
            if code == settings.LANGUAGE_CODE:
                continue
            folder = base / "locale" / code / "LC_MESSAGES"
            folder.mkdir(parents=True, exist_ok=True)
            for domain, msgids in found.items():
                po = folder / f"{domain}.po"
                old = pofile.read_po(po.open("rb"), locale=code) if po.exists() else Catalog(locale=code)
                new = Catalog(locale=code, project="Wine Explorer", charset="utf-8", fuzzy=False)
                for msgid in sorted(msgids):
                    previous = old.get(msgid)
                    new.add(msgid, previous.string if previous else "")
                untranslated = [m.id for m in new if m.id and not m.string]
                todo += len(untranslated)
                with po.open("wb") as fh:
                    pofile.write_po(fh, new, width=110, sort_output=True, omit_header=False)
                with (folder / f"{domain}.mo").open("wb") as fh:
                    mofile.write_mo(fh, new)
                self.stdout.write(f"{code}/{domain} : {len(msgids)} chaînes, {len(untranslated)} à traduire")
                if missing:
                    for msgid in untranslated:
                        self.stdout.write(f"  - {msgid}")
        if check and todo:
            raise CommandError(f"{todo} chaîne(s) sans traduction.")

    # ------------------------------------------------------------------
    @staticmethod
    def _python(source: str) -> set[str]:
        from babel.messages.extract import extract

        out = set()
        for _lineno, message, _comments, _context in extract(
            "python", io.BytesIO(source.encode("utf-8")), keywords=KEYWORDS
        ):
            out.add(message if isinstance(message, str) else message[0])
        return out

    @staticmethod
    def _template(pseudo_python: str) -> set[str]:
        """`templatize` rend du pseudo-Python : gettext(u'…') pour chaque balise de traduction."""
        import ast

        out = set()
        for literal in TEMPLATE_CALL.findall(pseudo_python):
            out.add(ast.literal_eval(literal))
        return out

    def _interface(self, base: Path) -> set[str]:
        out = set()
        for path in (base / "templates").rglob("*.html"):
            out |= self._template(templatize(path.read_text(encoding="utf-8"), origin=str(path)))
        for path in (base / "apps").rglob("*.py"):
            if "migrations" in path.parts or "tests" in path.parts:
                continue
            out |= self._python(path.read_text(encoding="utf-8"))
        return out

    @staticmethod
    def _scripts(base: Path) -> set[str]:
        from babel.messages.extract import extract

        out = set()
        for path in (base / "static" / "js").glob("*.js"):
            with path.open("rb") as fh:
                for _lineno, message, _comments, _context in extract(
                    "javascript", fh, keywords={"_": None, "gettext": None}
                ):
                    out.add(message if isinstance(message, str) else message[0])
        return out

    @staticmethod
    def _data() -> set[str]:
        """Chaînes de la base affichées avec le filtre `tr` (voir apps/catalog/i18n.py)."""
        from apps.catalog.models import Appellation, Aroma, AromaFamily, Grape, Region, WineProfile
        from apps.molecules.models import Molecule, NaturalSource, Occurrence, Reference
        from apps.nose import sensory

        out: set[str] = set()

        def add(*values):
            for value in values:
                if isinstance(value, str) and HAS_LETTERS.search(value):
                    out.add(value)

        for fam in AromaFamily.objects.all():
            add(fam.name)
        for aroma in Aroma.objects.all():
            add(aroma.name)
        for region in Region.objects.all():
            add(region.name, region.description)
        for grape in Grape.objects.all():
            add(grape.description, grape.origin)
        for app in Appellation.objects.all():
            add(app.description)
        for profile in WineProfile.objects.all():
            add(profile.description, profile.serving_temp, *profile.pairings)
        for mol in Molecule.objects.all():
            add(mol.name, mol.odor, mol.threshold, mol.description)
        for src in NaturalSource.objects.filter(imported=False):
            add(src.name, src.description)
        for occ in Occurrence.objects.filter(imported=False):
            add(occ.note)
        for ref in Reference.objects.all():
            add(ref.note)
        for term in sensory.TERMS:
            add(term.label, *term.synonyms)
        return out
