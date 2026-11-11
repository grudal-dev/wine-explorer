"""Traduction du contenu de la base (arômes, descriptions, accords…) à l'affichage.

Les données sont saisies en français ; leur traduction vit dans le même catalogue
gettext que l'interface (locale/<langue>/LC_MESSAGES/django.po), avec le texte
français pour identifiant. Une chaîne absente du catalogue reste en français.
"""

from django import template

from apps.catalog.i18n import tr as _tr
from apps.catalog.i18n import tr_list as _tr_list

register = template.Library()


@register.filter
def tr(value):
    """{{ aroma.name|tr }} : la valeur traduite dans la langue active."""
    return _tr(value)


@register.filter
def tr_list(values):
    """{{ profile.pairings|tr_list|join:", " }}"""
    return _tr_list(values)
