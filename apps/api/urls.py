from django.urls import path

from . import views

app_name = "api"

urlpatterns = [
    path("auth/signup/", views.signup, name="signup"),
    path("auth/login/", views.login, name="login"),
    path("auth/logout/", views.logout, name="logout"),
    path("me/", views.me, name="me"),
    path("today/", views.today, name="today"),
    path("blindtest/games/", views.blindtest_games, name="blindtest_games"),
    path("blindtest/games/<uuid:public_id>/", views.blindtest_game, name="blindtest_game"),
    path("blindtest/games/<uuid:public_id>/guess/", views.blindtest_guess, name="blindtest_guess"),
    path("blindtest/games/<uuid:public_id>/give-up/", views.blindtest_give_up, name="blindtest_give_up"),
    path("blindtest/suggest/", views.blindtest_suggest, name="blindtest_suggest"),
    path("hotcold/", views.hotcold_current, name="hotcold"),
    path("hotcold/new/", views.hotcold_new, name="hotcold_new"),
    path("hotcold/guess/", views.hotcold_guess, name="hotcold_guess"),
    path("hotcold/give-up/", views.hotcold_give_up, name="hotcold_give_up"),
    path("hotcold/suggest/", views.hotcold_suggest, name="hotcold_suggest"),
    path("rankings/", views.ranking, name="rankings"),
    path("players/<str:username>/", views.player, name="player"),
    path("wines/", views.wines, name="wines"),
    path("wines/<slug:slug>/", views.wine, name="wine"),
]
