from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from apps.agenda.models import Promotion
from apps.evaluation.models import Inscription
from .models import Prerequis, Profil

User = get_user_model()


class NouvelUtilisateurForm(forms.Form):
    first_name = forms.CharField(label="Prénom", max_length=150)
    last_name = forms.CharField(label="Nom", max_length=150)
    email = forms.EmailField(label="E-mail")
    username = forms.CharField(label="Identifiant de connexion", max_length=150)
    role = forms.ChoiceField(label="Rôle", choices=Profil.Role.choices, initial=Profil.Role.APPRENANT)
    promotion = forms.ModelChoiceField(label="Promotion (apprenant)", required=False,
                                       queryset=Promotion.objects.filter(active=True))
    password = forms.CharField(label="Mot de passe provisoire", widget=forms.PasswordInput,
                               help_text="À communiquer à la personne ; elle pourra le changer depuis son profil.")

    def clean_username(self):
        u = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=u).exists():
            raise forms.ValidationError("Cet identifiant est déjà utilisé.")
        return u

    def clean_email(self):
        e = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=e).exists():
            raise forms.ValidationError("Un compte existe déjà avec cet e-mail.")
        return e

    def clean(self):
        data = super().clean()
        if data.get("password"):
            validate_password(data["password"], User(username=data.get("username", ""),
                                                     email=data.get("email", "")))
        return data


class CompteForm(forms.ModelForm):
    """Identité du compte modifiable par son titulaire."""
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
        labels = {"first_name": "Prénom", "last_name": "Nom", "email": "E-mail"}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["email"].required = True

    def clean_email(self):
        e = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=e).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Un autre compte utilise déjà cet e-mail.")
        return e


class CompteAdminForm(CompteForm):
    """Version admin : identifiant, activation, rôle, promotion, nouveau mot de passe."""
    role = forms.ChoiceField(label="Rôle", choices=Profil.Role.choices)
    promotion = forms.ModelChoiceField(label="Promotion (apprenant)", required=False,
                                       queryset=Promotion.objects.filter(active=True))
    statut_inscription = forms.ChoiceField(
        label="Statut de l'inscription", required=False, choices=Inscription.Statut.choices,
        help_text="Seule une inscription « En cours » donne accès aux contenus de la formation.")
    nouveau_mdp = forms.CharField(label="Nouveau mot de passe", required=False, widget=forms.PasswordInput,
                                  help_text="Laisser vide pour ne pas le changer.")

    class Meta(CompteForm.Meta):
        fields = ["username", "first_name", "last_name", "email", "is_active"]
        labels = {**CompteForm.Meta.labels, "username": "Identifiant", "is_active": "Compte actif"}

    def clean_username(self):
        u = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=u).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Cet identifiant est déjà utilisé.")
        return u

    def clean_nouveau_mdp(self):
        mdp = self.cleaned_data.get("nouveau_mdp")
        if mdp:
            validate_password(mdp, self.instance)
        return mdp


class ProfilForm(forms.ModelForm):
    class Meta:
        model = Profil
        fields = ["photo", "telephone", "structure", "specialite", "bio"]
        widgets = {"bio": forms.Textarea(attrs={"rows": 3})}

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if photo and hasattr(photo, "size") and photo.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Photo trop lourde (5 Mo maximum).")
        return photo


class PrerequisForm(forms.ModelForm):
    class Meta:
        model = Prerequis
        exclude = ["profil"]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        for f in self.fields.values():
            f.required = False

    def clean(self):
        d = super().clean()
        for nom in self.fields:  # champ non soumis = valeur actuelle conservée
            if not d.get(nom):
                d[nom] = getattr(self.instance, nom)
        return d
