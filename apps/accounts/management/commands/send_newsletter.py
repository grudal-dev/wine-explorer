"""Envoie la newsletter aux abonnés actifs.

    python manage.py send_newsletter --subject "Les vins de novembre" --body-file lettre.txt --dry-run
    python manage.py send_newsletter --subject "..." --body-file lettre.txt

Chaque e-mail porte un lien de désinscription personnel et l'en-tête List-Unsubscribe.
"""

from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import NewsletterSubscription


class Command(BaseCommand):
    help = "Envoie la newsletter aux abonnés actifs."

    def add_arguments(self, parser):
        parser.add_argument("--subject", required=True)
        parser.add_argument("--body-file", required=True, help="Fichier texte du message.")
        parser.add_argument("--dry-run", action="store_true", help="Lister les destinataires sans envoyer.")

    def handle(self, *args, subject, body_file, dry_run, **options):
        try:
            body = open(body_file, encoding="utf-8").read().strip()
        except OSError as exc:
            raise CommandError(f"Lecture impossible : {exc}") from exc
        subs = NewsletterSubscription.objects.filter(
            unsubscribed_at__isnull=True).exclude(user__email="").select_related("user")
        self.stdout.write(f"{subs.count()} abonné(s) actif(s).")
        if dry_run:
            for s in subs:
                self.stdout.write(f"  {s.user.email}")
            return
        connection = get_connection()
        sent = 0
        for s in subs:
            link = settings.SITE_URL + reverse("accounts:newsletter_unsubscribe", args=[s.token])
            text = f"{body}\n\n--\nPour vous désinscrire : {link}\n"
            EmailMessage(subject, text, to=[s.user.email], connection=connection,
                         headers={"List-Unsubscribe": f"<{link}>"}).send()
            s.last_sent_at = timezone.now()
            s.save(update_fields=["last_sent_at"])
            sent += 1
        self.stdout.write(self.style.SUCCESS(f"{sent} e-mail(s) envoyé(s)."))
