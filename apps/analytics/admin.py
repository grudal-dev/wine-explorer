from django.contrib import admin

from .models import Event, PageView


class ReadOnly(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PageView)
class PageViewAdmin(ReadOnly):
    list_display = ("created_at", "path", "status", "source", "utm_campaign", "device", "browser", "visitor", "user",
                    "engaged_ms", "scroll")
    list_filter = ("day", "source", "device", "browser", "os", "status", "is_entry", "language")
    search_fields = ("path", "referrer_host", "utm_campaign", "visitor", "user__username")
    date_hierarchy = "created_at"
    list_select_related = ("user",)


@admin.register(Event)
class EventAdmin(ReadOnly):
    list_display = ("created_at", "name", "path", "props", "visitor", "user")
    list_filter = ("name", "day")
    search_fields = ("name", "visitor", "user__username")
    date_hierarchy = "created_at"
    list_select_related = ("user",)
