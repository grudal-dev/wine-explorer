from django.urls import path

from . import views

app_name = "embeddings"
urlpatterns = [
    path("", views.taste_map, name="map"),
    path("api/carte/", views.api_map, name="api_map"),
    path("api/voisins/", views.api_neighbours, name="api_neighbours"),
    path("fiche/<str:node_id>/", views.cousins_panel, name="panel"),
]
