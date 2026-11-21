from django.urls import path

from . import views_compare as views

app_name = "compare"
urlpatterns = [
    path("", views.start, name="start"),
    path("<slug:a>/<slug:b>/", views.duel, name="duel"),
]
