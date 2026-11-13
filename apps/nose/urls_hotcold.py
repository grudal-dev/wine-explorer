from django.urls import path

from . import views

app_name = "hotcold"
urlpatterns = [
    path("", views.hot_cold, name="game"),
    path("essai/", views.hot_cold_guess, name="guess"),
    path("nouveau/", views.hot_cold_new, name="new"),
    path("abandon/", views.hot_cold_give_up, name="give_up"),
]
