from django.contrib import admin
from django.urls import include, path

from apps.catalog import views as catalog_views

urlpatterns = [
    path("", catalog_views.home, name="home"),
    path("catalogue/", include("apps.catalog.urls")),
    path("graphe/", include("apps.explorer.urls")),
    path("blind-test/", include("apps.blindtest.urls")),
    path("le-nez/", include("apps.nose.urls")),
    path("compte/", include("apps.accounts.urls")),
    path("admin/", admin.site.urls),
]

admin.site.site_header = "Terroirs · administration"
admin.site.site_title = "Terroirs"
