from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "nose"
urlpatterns = [
    path("", views.nose, name="nose"),
    path("api/aromes/", views.api_aromas, name="api_aromas"),
    # Le chaud-froid n'est plus un mode du Nez : il vit sous /chaud-froid/ (anciens liens conservés).
    path("chaud-froid/", RedirectView.as_view(pattern_name="hotcold:game", permanent=True)),
]
