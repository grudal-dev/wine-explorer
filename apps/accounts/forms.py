from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

from .models import NewsletterSubscription


class SignupForm(forms.ModelForm):
    """Inscription en quatre champs : nom au classement, e-mail, un seul mot de passe, majorité.
    Le mot de passe se montre au besoin (bouton « Afficher ») plutôt que d'être tapé deux fois."""

    email = forms.EmailField(label=_("Adresse e-mail"), required=True,
                             help_text=_("Jamais affichée. Sert seulement à retrouver votre compte."))
    password = forms.CharField(
        label=_("Mot de passe"), strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "data-reveal": ""}),
        help_text=_("8 caractères au moins, pas trop courant."))
    # Âge légal : simple attestation, la date de naissance n'est pas collectée (minimisation).
    adult = forms.BooleanField(
        required=True, label=_("Je certifie avoir 18 ans ou plus"),
        error_messages={"required": _("Vous devez avoir 18 ans ou plus pour créer un compte.")})
    # Opt-in : jamais coché d'office, la réponse est libre et sans effet sur le compte.
    newsletter = forms.BooleanField(
        required=False, initial=False,
        label=_("Recevoir la newsletter (environ une fois par mois, désinscription en un clic)"))

    class Meta:
        model = User
        fields = ("username", "email")
        labels = {"username": _("Nom au classement")}
        help_texts = {"username": _("Lettres, chiffres et . _ - ; visible par tous.")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({"autocomplete": "username", "autofocus": True})
        self.fields["email"].widget.attrs.update({"autocomplete": "email"})

    def clean_username(self):
        name = self.cleaned_data["username"]
        if User.objects.filter(username__iexact=name).exists():
            raise forms.ValidationError(_("Ce nom est déjà pris."))
        return name

    def _post_clean(self):
        super()._post_clean()
        password = self.cleaned_data.get("password")
        if password:
            try:
                password_validation.validate_password(password, self.instance)
            except forms.ValidationError as error:
                self.add_error("password", error)

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("Un compte existe déjà avec cette adresse."))
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        if commit and self.cleaned_data.get("newsletter"):
            NewsletterSubscription.subscribe(user)
        return user
