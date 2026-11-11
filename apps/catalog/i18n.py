"""Traduction à la volée des chaînes venues de la base de données."""

from __future__ import annotations

import re

from django.utils.translation import get_language, gettext


def is_french() -> bool:
    return (get_language() or "fr").startswith("fr")


def tr(value):
    """Traduit une chaîne de la base. Les valeurs vides et non textuelles passent telles quelles."""
    if not value or not isinstance(value, str) or is_french():
        return value
    return gettext(value)


def all_labels(label) -> list[str]:
    """Le libellé dans chaque langue du site, sans doublon : sert aux index de recherche."""
    from django.conf import settings
    from django.utils.translation import override

    out = []
    for code, _name in settings.LANGUAGES:
        with override(code):
            text = str(tr(label)) if isinstance(label, str) else str(label)
        if text and text not in out:
            out.append(text)
    return out


def tr_list(values) -> list:
    return [tr(v) for v in values or []]


# Justifications des liens vin → molécule, produites en français par load_molecules et stockées
# telles quelles : on les reconnaît à leur forme pour les traduire à l'affichage.
_REASONS = [
    (re.compile(r"^(?P<grape>.+) \((?P<share>\d+) % de l'encépagement\)$"),
     lambda m: gettext("%(grape)s (%(share)s %% de l'encépagement)") % m.groupdict()),
    (re.compile(r"^Style (?P<style>.+)$"),
     lambda m: gettext("Style %(style)s") % {"style": _style(m["style"])}),
    (re.compile(r"^Vin (?P<color>rouge|blanc|rosé)$"),
     lambda m: gettext("Vin %(color)s") % {"color": tr(m["color"].capitalize()).lower()}),
    (re.compile(r"^Au nez : (?P<aroma>.+) \((?P<level>discret|présent|dominant)\)$"),
     lambda m: gettext("Au nez : %(aroma)s (%(level)s)") % {
         "aroma": tr(m["aroma"]), "level": tr(m["level"].capitalize()).lower()}),
    (re.compile(r"^Famille (?P<family>.+) au nez \((?P<aromas>.+)\)$"),
     lambda m: gettext("Famille %(family)s au nez (%(aromas)s)") % {
         "family": _family(m["family"]), "aromas": ", ".join(tr(a) for a in m["aromas"].split(", "))}),
]


def _style(lowered: str) -> str:
    from .models import Style

    for _, label in Style.choices:
        if str(label).lower() == lowered:  # str(label) : libellé dans la langue active
            return str(label).lower()
    return _from_french(Style, lowered)


def _from_french(choices, lowered: str) -> str:
    from django.utils.translation import override

    with override("fr"):
        french = {str(label).lower(): value for value, label in choices.choices}
    value = french.get(lowered)
    return str(choices(value).label).lower() if value else lowered


def _family(lowered: str) -> str:
    from .models import AromaFamily

    for name in AromaFamily.objects.values_list("name", flat=True):
        if name.lower() == lowered:
            return tr(name).lower()
    return lowered


def tr_reason(label: str) -> str:
    """« Au nez : violette (dominant) » → « On the nose: violet (dominant) »."""
    if is_french() or not label:
        return label
    for pattern, render in _REASONS:
        m = pattern.match(label)
        if m:
            text = render(m)
            return text[:1].upper() + text[1:]
    return gettext(label)
