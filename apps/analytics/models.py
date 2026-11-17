"""Mesure d'audience sans cookie.

Aucune adresse IP n'est conservée. Un visiteur est reconnu, pour une seule journée, par une empreinte
`sha256(clé secrète + jour + IP + navigateur)` tronquée : elle change chaque jour et ne permet pas de suivre
une personne d'un jour à l'autre. Avec une durée de conservation limitée (`ANALYTICS_RETENTION_DAYS`), ce
fonctionnement correspond à l'exemption de consentement de la CNIL pour la mesure d'audience.
"""

from django.conf import settings
from django.db import models


class PageView(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    day = models.DateField(db_index=True)
    visitor = models.CharField("visiteur du jour", max_length=16, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="+")
    path = models.CharField("page", max_length=300, db_index=True)
    query = models.CharField(max_length=300, blank=True)
    status = models.PositiveSmallIntegerField(default=200)
    language = models.CharField("langue de la page", max_length=8, blank=True)
    browser_language = models.CharField("langue du navigateur", max_length=16, blank=True)
    is_entry = models.BooleanField("page d'entrée", default=False)
    source = models.CharField(max_length=40, blank=True, db_index=True)
    referrer_host = models.CharField("site d'origine", max_length=120, blank=True)
    referrer = models.CharField("adresse d'origine", max_length=500, blank=True)
    utm_source = models.CharField(max_length=80, blank=True)
    utm_medium = models.CharField(max_length=80, blank=True)
    utm_campaign = models.CharField(max_length=120, blank=True)
    utm_content = models.CharField(max_length=120, blank=True)
    device = models.CharField("appareil", max_length=10, blank=True)
    browser = models.CharField("navigateur", max_length=30, blank=True)
    os = models.CharField("système", max_length=20, blank=True)
    response_ms = models.PositiveIntegerField("temps de réponse (ms)", default=0)
    engaged_ms = models.PositiveIntegerField("temps passé (ms)", null=True, blank=True)
    scroll = models.PositiveSmallIntegerField("défilement max (%)", null=True, blank=True)

    class Meta:
        verbose_name = "page vue"
        verbose_name_plural = "pages vues"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["day", "visitor"]), models.Index(fields=["visitor", "path", "-created_at"])]

    def __str__(self):
        return f"{self.path} · {self.created_at:%d/%m %H:%M}"


class Event(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    day = models.DateField(db_index=True)
    visitor = models.CharField("visiteur du jour", max_length=16, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="+")
    name = models.CharField("événement", max_length=40, db_index=True)
    path = models.CharField("page", max_length=300, blank=True)
    props = models.JSONField("détails", default=dict, blank=True)

    class Meta:
        verbose_name = "événement"
        verbose_name_plural = "événements"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} · {self.created_at:%d/%m %H:%M}"
