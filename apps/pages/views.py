"""Pages d'information : à propos, contact, mentions légales, confidentialité."""

from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.core.mail import mail_admins
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext

from apps.catalog.models import Appellation, WineProfile

from .forms import ContactForm
from .models import ContactMessage

RETENTION_DAYS = 365
MAX_PER_HOUR = 5  # par session : assez pour un humain, trop peu pour un robot obstiné


def _legal():
    return {
        "publisher": settings.LEGAL_PUBLISHER, "address": settings.LEGAL_PUBLISHER_ADDRESS,
        "publisher_id": settings.LEGAL_PUBLISHER_ID, "director": settings.LEGAL_DIRECTOR or settings.LEGAL_PUBLISHER,
        "contact_email": settings.CONTACT_EMAIL, "host": settings.LEGAL_HOST,
        "reviewer": settings.DATA_REVIEWER,
    }


def about(request):
    return render(request, "pages/about.html", {
        **_legal(),
        "profiles": WineProfile.objects.count(),
        "appellations": Appellation.objects.count(),
    })


def legal(request):
    return render(request, "pages/legal.html", _legal())


def privacy(request):
    return render(request, "pages/privacy.html", {
        **_legal(), "analytics_days": int(getattr(settings, "ANALYTICS_RETENTION_DAYS", 395)),
        "contact_days": RETENTION_DAYS,
    })


def contact(request):
    form = ContactForm(request.POST or None, initial={"topic": request.GET.get("objet", "other")})
    if request.method == "POST" and form.is_valid():
        if form.cleaned_data["website"]:   # robot : on fait comme si de rien n'était
            return redirect("contact_sent")
        now = timezone.now().timestamp()
        recent = [t for t in request.session.get("contact_sent", []) if now - t < 3600]
        if len(recent) >= MAX_PER_HOUR:
            messages.error(request, gettext("Trop de messages envoyés d'ici. Réessayez dans une heure."))
            return render(request, "pages/contact.html", {"form": form, **_legal()})
        msg = ContactMessage.objects.create(**{k: form.cleaned_data[k] for k in ("name", "email", "topic", "message")})
        request.session["contact_sent"] = [*recent, now]
        ContactMessage.objects.filter(created_at__lt=timezone.now() - timedelta(days=RETENTION_DAYS)).delete()
        if settings.ADMINS:
            mail_admins(f"Contact : {msg.get_topic_label()}", f"{msg.name} <{msg.email}>\n\n{msg.message}",
                        fail_silently=True)
        return redirect("contact_sent")
    return render(request, "pages/contact.html", {"form": form, **_legal()})


def contact_sent(request):
    return render(request, "pages/contact_sent.html")
