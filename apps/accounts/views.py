from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext
from django.views.decorators.http import require_POST

from apps.analytics.tracking import track
from apps.blindtest.models import Game
from apps.blindtest.views import spoiler_profile_id, stats_for
from apps.nose import hotcold

from . import rankings
from .forms import SignupForm
from .models import NewsletterSubscription


def signup(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile")
    form = SignupForm(request.POST or None)
    # Retour là où l'on était (la partie qu'on vient de finir) ; sinon le profil.
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    if not url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        nxt = ""
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        track(request, "signup")
        messages.success(
            request, gettext("Bienvenue, %(name)s. Vos parties sont enregistrées.") % {"name": user.username})
        return redirect(nxt or "accounts:profile")
    return render(request, "registration/signup.html", {"form": form, "next": nxt,
                                                        "points": request.GET.get("points", "")})


@login_required
@require_POST
def delete_account(request):
    """Droit à l'effacement : le compte part avec ses parties (suppression en cascade)."""
    user = request.user
    if not user.check_password(request.POST.get("password", "")):
        messages.error(request, gettext("Mot de passe incorrect : le compte n'a pas été supprimé."))
        return redirect("accounts:profile")
    logout(request)
    user.delete()
    messages.success(request, gettext("Votre compte et vos données ont été supprimés."))
    return redirect("home")


@login_required
def profile(request):
    games = request.user.games.select_related("profile__appellation")[:30]
    return render(request, "accounts/profile.html", {
        "owner": request.user, "is_self": True,
        "stats": stats_for(request.user), "games": games,
        "hotcold_games": hotcold.visible_history(request.user, request, timezone.localdate()),
        "newsletter": NewsletterSubscription.objects.filter(
            user=request.user, unsubscribed_at__isnull=True).exists(),
    })


@login_required
@require_POST
def newsletter_toggle(request):
    if request.POST.get("subscribe") == "1":
        NewsletterSubscription.subscribe(request.user)
        track(request, "newsletter_subscribe")
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
             .exclude(profile_id=spoiler_profile_id(request))  # vin du jour : pas de spoiler
             .select_related("profile__appellation")[:30])
    return render(request, "accounts/profile.html", {
        "owner": owner, "is_self": False, "stats": stats_for(owner), "games": games,
        "hotcold_games": hotcold.visible_history(owner, request, timezone.localdate()),
    })


def ranking(request):
    # Le classement, c'est le blind test du jour ; le chaud-froid, bonus, garde son tableau à part.
    game = request.GET.get("jeu", "blindtest")
    if game not in rankings.PUBLIC_GAMES:
        game = "blindtest"
    today = timezone.localdate()
    return render(request, "accounts/ranking.html", {
        "game": game, "day": today, **rankings.standings(game, today),
    })
