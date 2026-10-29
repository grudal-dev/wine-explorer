from django.urls import path

from . import views

app_name = "nose"
urlpatterns = [
    path("", views.nose, name="nose"),
    path("api/aromes/", views.api_aromas, name="api_aromas"),
]
