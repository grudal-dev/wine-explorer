from django.urls import path

from . import views

app_name = "nose"
urlpatterns = [
    path("", views.nose, name="nose"),
    path("api/aromes/", views.api_aromas, name="api_aromas"),
    path("chaud-froid/", views.hot_cold, name="hot_cold"),
    path("chaud-froid/essai/", views.hot_cold_guess, name="hot_cold_guess"),
    path("chaud-froid/nouveau/", views.hot_cold_new, name="hot_cold_new"),
    path("chaud-froid/abandon/", views.hot_cold_give_up, name="hot_cold_give_up"),
]
