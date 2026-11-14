from django.contrib import admin

from .models import NewsletterSubscription


@admin.register(NewsletterSubscription)
class NewsletterSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "email", "subscribed_at", "unsubscribed_at", "last_sent_at")
    list_filter = ("unsubscribed_at",)
    search_fields = ("user__username", "user__email")
    readonly_fields = ("token",)

    @admin.display(description="E-mail")
    def email(self, obj):
        return obj.user.email
