from django.contrib import admin

from .models import Molecule, NaturalSource, Occurrence, ProfileMolecule, Reference


class OccurrenceInline(admin.TabularInline):
    model = Occurrence
    extra = 0
    autocomplete_fields = ("source", "reference")


@admin.register(Molecule)
class MoleculeAdmin(admin.ModelAdmin):
    list_display = ("name", "family", "origin", "formula", "universal")
    list_filter = ("family", "origin", "universal")
    search_fields = ("name", "name_en", "synonyms")
    filter_horizontal = ("aromas", "references")
    inlines = [OccurrenceInline]


@admin.register(NaturalSource)
class NaturalSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "latin_name", "aroma")
    list_filter = ("kind",)
    search_fields = ("name", "latin_name")


@admin.register(Reference)
class ReferenceAdmin(admin.ModelAdmin):
    list_display = ("key", "short", "title", "doi")
    search_fields = ("key", "authors", "title")


@admin.register(ProfileMolecule)
class ProfileMoleculeAdmin(admin.ModelAdmin):
    list_display = ("profile", "molecule", "strength", "basis")
    list_filter = ("basis", "strength", "molecule")
    search_fields = ("profile__name", "molecule__name")
