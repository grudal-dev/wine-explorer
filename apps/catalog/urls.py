from django.urls import path

from . import views

app_name = "catalog"
urlpatterns = [
    path("", views.index, name="index"),
    path("vins/<slug:slug>/", views.profile_detail, name="profile"),
    path("appellations/<slug:slug>/", views.appellation_detail, name="appellation"),
    path("regions/<slug:slug>/", views.region_detail, name="region"),
    path("cepages/", views.grape_list, name="grapes"),
    path("cepages/<slug:slug>/", views.grape_detail, name="grape"),
    path("aromes/", views.aroma_list, name="aromas"),
    path("aromes/<slug:slug>/", views.aroma_detail, name="aroma"),
    path("sources/", views.sources, name="sources"),
]
