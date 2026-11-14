from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.utils.translation import gettext

from apps.blindtest.models import Game
from apps.blindtest.views import stats_for

from . import rankings
from .forms import SignupForm
from .models import NewsletterSubscription


def signup(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(
            request, gettext("Bienvenue, %(name)s. Vos parties sont enregistrées.") % {"name": user.username})
        return redirect("accounts:profile")
    return render(request, "registration/signup.html", {"form": form})


@login_required
def profile(request):
    games = request.user.games.select_related("profile__appellation")[:30]
    return render(request, "accounts/profile.html", {
        "owner": request.user, "is_self": True,
        "stats": stats_for(request.user), "games": games,
        "newsletter": NewsletterSubscription.objects.filter(
            user=request.user, unsubscribed_at__isnull=True).exists(),
    })


@login_required
@require_POST
def newsletter_toggle(request):
    if request.POST.get("subscribe") == "1":
        NewsletterSubscription.subscribe(request.user)
        messages.success(request, gettext("Vous êtes inscrit à la newsletter."))
    else:
        NewsletterSubscription.unsubscribe(request.user)
        messages.success(request, gettext("Vous êtes désinscrit de la newsletter."))
    return redirect("accounts:profile")


def newsletter_unsubscribe(request, token):
    """Désinscription en un clic depuis l'e-mail (sans connexion). GET = confirmation, POST = action."""
    sub = get_object_or_404(NewsletterSubscription, token=token)
    if request.method == "POST":
        NewsletterSubscription.unsubscribe(sub.user)
        sub.refresh_from_db()
    return render(request, "accounts/newsletter_unsubscribe.html", {"sub": sub})


def player(request, username):
    """Profil public : les parties terminées d'un joueur (jamais celles en cours, qui trahiraient le vin)."""
    owner = get_object_or_404(User, username=username)
    if request.user.is_authenticated and request.user == owner:
        return redirect("accounts:profile")
    games = (owner.games.exclude(status=Game.Status.PLAYING)
             .select_related("profile__appellation")[:30])
    return render(request, "accounts/profile.html", {
        "owner": owner, "is_self": False, "stats": stats_for(owner), "games": games,
    })


def ranking(request):
    game = request.GET.get("jeu", "total")
    if game not in rankings.GAMES:
        game = "total"
    today = timezone.localdate()
    return render(request, "accounts/ranking.html", {
        "game": game, "day": today, **rankings.standings(game, today),
    })
