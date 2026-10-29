from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Q, Sum
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.blindtest.models import Game
from apps.blindtest.views import leaderboard, stats_for

from .forms import SignupForm


def signup(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f"Bienvenue, {user.username}. Vos parties sont enregistrées.")
        return redirect("accounts:profile")
    return render(request, "registration/signup.html", {"form": form})


@login_required
def profile(request):
    games = request.user.games.select_related("profile__appellation")[:30]
    return render(request, "accounts/profile.html", {
        "stats": stats_for(request.user), "games": games,
    })


def ranking(request):
    today = timezone.localdate()
    all_time = (
        Game.objects.filter(user__isnull=False).exclude(status=Game.Status.PLAYING)
        .values("user__username")
        .annotate(total=Sum("score"), played=Count("id"),
                  won=Count("id", filter=Q(status=Game.Status.WON)), best=Max("score"))
        .order_by("-total")[:20]
    )
    return render(request, "accounts/ranking.html", {
        "today": leaderboard(today, limit=20), "all_time": all_time, "day": today,
    })
