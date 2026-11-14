from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"
urlpatterns = [
    path("inscription/", views.signup, name="signup"),
    path("connexion/", auth_views.LoginView.as_view(), name="login"),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="logout"),
    path("profil/", views.profile, name="profile"),
    path("joueur/<str:username>/", views.player, name="player"),
    path("newsletter/", views.newsletter_toggle, name="newsletter"),
    path("newsletter/desinscription/<str:token>/", views.newsletter_unsubscribe, name="newsletter_unsubscribe"),
    path("classement/", views.ranking, name="ranking"),
]
