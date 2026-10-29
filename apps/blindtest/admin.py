from django.contrib import admin

from .models import Game, Guess


class GuessInline(admin.TabularInline):
    model = Guess
    extra = 0
    readonly_fields = ("raw", "kind", "label", "verdict", "feedback", "counted", "created_at")
    can_delete = False


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ("profile", "user", "mode", "day", "status", "score", "created_at")
    list_filter = ("mode", "status", "day")
    search_fields = ("profile__name", "user__username")
    inlines = [GuessInline]
    readonly_fields = ("public_id", "created_at", "finished_at")
