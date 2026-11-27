from django.contrib import admin

from .models import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("created_at", "email", "topic", "handled")
    list_filter = ("handled", "topic")
    list_editable = ("handled",)
    search_fields = ("email", "name", "message")
    readonly_fields = ("created_at", "name", "email", "topic", "message")
