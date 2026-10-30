from django.urls import path

from . import views

app_name = "molecules"
urlpatterns = [
    path("", views.explorer, name="explorer"),
    path("liste/", views.molecule_list, name="list"),
    path("sources/", views.bibliography, name="bibliography"),
    path("nature/<slug:slug>/", views.source_detail, name="source"),
    path("api/graphe/", views.api_graph, name="api_graph"),
    path("api/recherche/", views.api_search, name="api_search"),
    path("fiche/<str:node_id>/", views.panel, name="panel"),
    path("<slug:slug>/", views.molecule_detail, name="molecule"),
]
