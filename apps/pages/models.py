"""Messages reçus par le formulaire de contact : lus dans l'administration, effacés au bout d'un an."""

from django.db import models


class ContactMessage(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    name = models.CharField("nom", max_length=120, blank=True)
    email = models.EmailField("adresse e-mail")
    topic = models.CharField("objet", max_length=20, default="other")
    message = models.TextField("message", max_length=4000)
    handled = models.BooleanField("traité", default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "message de contact"
        verbose_name_plural = "messages de contact"

    def __str__(self) -> str:
        return f"{self.email} · {self.created_at:%d/%m/%Y}"

    def get_topic_label(self) -> str:
        from .forms import TOPICS

        return str(dict(TOPICS).get(self.topic, self.topic))
