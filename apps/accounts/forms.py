from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _


class SignupForm(UserCreationForm):
    email = forms.EmailField(label=_("Adresse e-mail"), required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")
        labels = {"username": _("Nom d'utilisateur")}

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("Un compte existe déjà avec cette adresse."))
        return email
