from django.contrib import admin
from django.conf.urls.i18n import i18n_patterns
from django.urls import include, path
from django.contrib.sitemaps.views import sitemap
from django.views.i18n import JavaScriptCatalog

from apps.catalog.i18n import set_language

from apps.catalog import seo, views as catalog_views

# Hors préfixe de langue : fichiers pour les robots, bascule de langue, API mobile (langue par Accept-Language)
# et administration.
urlpatterns = [
    path("robots.txt", seo.robots_txt, name="robots"),
    path("sitemap.xml", sitemap, {"sitemaps": seo.SITEMAPS}, name="sitemap"),
    path("i18n/setlang/", set_language, name="set_language"),  # changement de langue
    path("api/v1/", include("apps.api.urls")),
    path("admin/", admin.site.urls),
]

# Le site : français sans préfixe, anglais sous /en/. Une adresse par langue, pour que chacune soit indexable.
urlpatterns += i18n_patterns(
    path("", catalog_views.home, name="home"),
    path("catalogue/", include("apps.catalog.urls")),
    path("graphe/", include("apps.explorer.urls")),
    path("blind-test/", include("apps.blindtest.urls")),
    path("le-nez/", include("apps.nose.urls")),
    path("chaud-froid/", include("apps.nose.urls_hotcold")),
    path("molecules/", include("apps.molecules.urls")),
    path("carte/", include("apps.embeddings.urls")),
    path("compte/", include("apps.accounts.urls")),
    path("jsi18n/", JavaScriptCatalog.as_view(packages=["apps.catalog"]), name="javascript-catalog"),
    prefix_default_language=False,
)

admin.site.site_header = "Wine Explorer · administration"
admin.site.site_title = "Wine Explorer"
