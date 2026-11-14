from django.contrib import admin
from django.urls import include, path
from django.views.i18n import JavaScriptCatalog

from apps.catalog import views as catalog_views

urlpatterns = [
    path("", catalog_views.home, name="home"),
    path("catalogue/", include("apps.catalog.urls")),
    path("graphe/", include("apps.explorer.urls")),
    path("blind-test/", include("apps.blindtest.urls")),
    path("le-nez/", include("apps.nose.urls")),
    path("chaud-froid/", include("apps.nose.urls_hotcold")),
    path("molecules/", include("apps.molecules.urls")),
    path("carte/", include("apps.embeddings.urls")),
    path("compte/", include("apps.accounts.urls")),
    path("i18n/", include("django.conf.urls.i18n")),  # changement de langue (set_language)
    path("jsi18n/", JavaScriptCatalog.as_view(packages=["apps.catalog"]), name="javascript-catalog"),
    path("admin/", admin.site.urls),
]

admin.site.site_header = "Wine Explorer · administration"
admin.site.site_title = "Wine Explorer"
