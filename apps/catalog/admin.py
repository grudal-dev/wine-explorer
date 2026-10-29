from django.contrib import admin

from .models import (
    Appellation,
    Aroma,
    AromaFamily,
    Country,
    Grape,
    ProfileAroma,
    ProfileGrape,
    Region,
    WineProfile,
)


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "kind", "country")
    list_filter = ("country", "kind", "parent")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Appellation)
class AppellationAdmin(admin.ModelAdmin):
    list_display = ("name", "region", "classification", "colors", "inao_code", "wikidata_id")
    list_filter = ("classification", "region__parent", "region")
    search_fields = ("name", "inao_code", "wikidata_id")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Grape)
class GrapeAdmin(admin.ModelAdmin):
    list_display = ("name", "skin", "origin")
    list_filter = ("skin",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


class AromaInline(admin.TabularInline):
    model = Aroma
    extra = 0
    prepopulated_fields = {"slug": ("name",)}


@admin.register(AromaFamily)
class AromaFamilyAdmin(admin.ModelAdmin):
    list_display = ("name", "order", "color")
    inlines = [AromaInline]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Aroma)
class AromaAdmin(admin.ModelAdmin):
    list_display = ("name", "family")
    list_filter = ("family",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


class ProfileGrapeInline(admin.TabularInline):
    model = ProfileGrape
    extra = 0
    autocomplete_fields = ("grape",)


class ProfileAromaInline(admin.TabularInline):
    model = ProfileAroma
    extra = 0
    autocomplete_fields = ("aroma",)


@admin.register(WineProfile)
class WineProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "appellation", "color", "style", "price_min", "price_max")
    list_filter = ("color", "style", "appellation__region__parent")
    search_fields = ("name", "appellation__name")
    inlines = [ProfileGrapeInline, ProfileAromaInline]
    autocomplete_fields = ("appellation",)
    prepopulated_fields = {"slug": ("name",)}
