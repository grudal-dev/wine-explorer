from django import forms
from django.utils.translation import gettext_lazy as _

TOPICS = [
    ("error", _("Une erreur dans une fiche")),
    ("data", _("Mes données personnelles")),
    ("partner", _("École, club, caviste : un partenariat")),
    ("other", _("Autre chose")),
]


class ContactForm(forms.Form):
    topic = forms.ChoiceField(label=_("Objet"), choices=TOPICS, initial="other")
    name = forms.CharField(label=_("Votre nom (facultatif)"), max_length=120, required=False)
    email = forms.EmailField(label=_("Votre adresse e-mail, pour vous répondre"))
    message = forms.CharField(label=_("Votre message"), max_length=4000, widget=forms.Textarea(attrs={"rows": 7}))
    # Piège à robots : champ masqué aux personnes, rempli par les robots qui remplissent tout.
    website = forms.CharField(label=_("Ne pas remplir"), required=False,
                              widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))
