from django.urls import path

from . import views

app_name = "blindtest"
urlpatterns = [
    path("", views.home, name="home"),
    path("nouvelle-partie/", views.start, name="start"),
    path("partie/<uuid:public_id>/", views.game_view, name="game"),
    path("partie/<uuid:public_id>/essai/", views.guess, name="guess"),
    path("partie/<uuid:public_id>/abandon/", views.give_up, name="give_up"),
    path("api/suggestions/", views.suggest, name="suggest"),
]
