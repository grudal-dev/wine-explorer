from django.urls import path

from . import views

urlpatterns = [
    path("a-propos/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),
    path("contact/merci/", views.contact_sent, name="contact_sent"),
    path("mentions-legales/", views.legal, name="legal"),
    path("confidentialite/", views.privacy, name="privacy"),
]
