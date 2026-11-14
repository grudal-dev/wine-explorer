from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

from .models import NewsletterSubscription


class SignupForm(UserCreationForm):
    email = forms.EmailField(label=_("Adresse e-mail"), required=True)
    # Âge légal : simple attestation, la date de naissance n'est pas collectée (minimisation).
    adult = forms.BooleanField(
        required=True, label=_("Je certifie avoir 18 ans ou plus"),
        error_messages={"required": _("Vous devez avoir 18 ans ou plus pour créer un compte.")})
    # Opt-in : jamais coché d'office, la réponse est libre et sans effet sur le compte.
    newsletter = forms.BooleanField(
        required=False, initial=False,
        label=_("Oui, je souhaite recevoir la newsletter de Wine Explorer"),
        help_text=_("Nouveautés, défis et découvertes, environ une fois par mois. "
                    "Désinscription possible à tout moment depuis votre profil ou d'un clic dans chaque e-mail."))

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")
        labels = {"username": _("Nom d'utilisateur")}

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("Un compte existe déjà avec cette adresse."))
        return email

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit and self.cleaned_data.get("newsletter"):
            NewsletterSubscription.subscribe(user)
        return user
