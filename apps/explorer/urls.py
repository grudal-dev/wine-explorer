from django.urls import path

from . import views

app_name = "explorer"
urlpatterns = [
    path("", views.explorer, name="explorer"),
    path("api/graphe/", views.api_graph, name="api_graph"),
    path("api/recherche/", views.api_search, name="api_search"),
    path("api/chemin/", views.api_path, name="api_path"),
    path("noeud/<str:node_id>/", views.node_panel, name="node"),
]
