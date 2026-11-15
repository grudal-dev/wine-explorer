from django.contrib import admin

from .models import HotColdGame


@admin.register(HotColdGame)
class HotColdGameAdmin(admin.ModelAdmin):
    list_display = ("day", "mode", "user", "device", "over", "updated_at")
    list_filter = ("mode", "over", "day")
    search_fields = ("user__username", "device")
