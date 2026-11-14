import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def new_token() -> str:
    return secrets.token_urlsafe(24)


class NewsletterSubscription(models.Model):
    """Consentement explicite (opt-in) à la newsletter, daté et révocable.

    Une ligne par compte. `unsubscribed_at` non nul = désinscrit : on garde la trace du
    consentement et de son retrait, mais plus aucun envoi n'est fait.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="newsletter")
    subscribed_at = models.DateTimeField(default=timezone.now)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    token = models.CharField(max_length=40, unique=True, default=new_token, editable=False)
    last_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("abonnement à la newsletter")
        verbose_name_plural = _("abonnements à la newsletter")
        ordering = ["-subscribed_at"]

    def __str__(self):
        return f"{self.user.email} ({'actif' if self.is_active else 'désinscrit'})"

    @property
    def is_active(self) -> bool:
        return self.unsubscribed_at is None

    @classmethod
    def subscribe(cls, user):
        sub, _created = cls.objects.get_or_create(user=user)
        if sub.unsubscribed_at is not None:
            sub.unsubscribed_at, sub.subscribed_at = None, timezone.now()
            sub.save(update_fields=["unsubscribed_at", "subscribed_at"])
        return sub

    @classmethod
    def unsubscribe(cls, user):
        cls.objects.filter(user=user, unsubscribed_at__isnull=True).update(unsubscribed_at=timezone.now())
