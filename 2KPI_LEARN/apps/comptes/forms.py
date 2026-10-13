import logging
from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from apps.agenda.models import Promotion
from apps.evaluation.models import Inscription
from .models import Prerequis, Profil

User = get_user_model()
logger = logging.getLogger(__name__)


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
        fields = ["photo", "categorie", "telephone", "structure", "specialite", "bio"]
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


class CreationCompteForm(forms.Form):
    """Création de compte en libre-service (bouton « Créer mon compte » du site vitrine).
    Le compte est un compte apprenant : il ne donne accès aux contenus qu'une fois rattaché
    à une promotion par l'administration (candidature acceptée)."""
    categorie = forms.ChoiceField(label="Je suis", choices=Profil.Categorie.choices, widget=forms.RadioSelect,
                                  initial=Profil.Categorie.ETUDIANT)
    first_name = forms.CharField(label="Prénom", max_length=150)
    last_name = forms.CharField(label="Nom", max_length=150)
    email = forms.EmailField(label="E-mail", help_text="Sert aussi d'identifiant de connexion.")
    telephone = forms.CharField(label="Téléphone (WhatsApp de préférence)", max_length=40)
    structure = forms.CharField(label="Université / école ou structure", max_length=200, required=False)
    promotion = forms.ModelChoiceField(
        label="Session souhaitée", required=False, empty_label="— Je choisirai plus tard —",
        queryset=Promotion.objects.none(),
        help_text="Facultatif : votre demande d'inscription sera transmise à l'équipe 2KPI.")
    password1 = forms.CharField(label="Mot de passe", strip=False, widget=forms.PasswordInput(
        attrs={"autocomplete": "new-password"}), help_text="8 caractères minimum, pas uniquement des chiffres.")
    password2 = forms.CharField(label="Confirmer le mot de passe", strip=False,
                                widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    site_web = forms.CharField(required=False, label="Site web", widget=forms.TextInput(
        attrs={"tabindex": "-1", "autocomplete": "off"}))  # piège anti-robots, masqué en CSS

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["promotion"].queryset = (
            Promotion.objects.filter(active=True, publiee_vitrine=True).select_related("formation")
            .order_by("date_debut"))
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        self.fields["telephone"].widget.attrs.update({"autocomplete": "tel", "type": "tel"})

    def clean_email(self):
        e = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=e).exists():
            raise forms.ValidationError("Un compte existe déjà avec cet e-mail : connectez-vous, ou utilisez "
                                        "« Mot de passe oublié » si vous ne vous en souvenez plus.")
        return e

    def clean(self):
        d = super().clean()
        p1, p2 = d.get("password1"), d.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Les deux mots de passe ne correspondent pas.")
        elif p1:
            try:
                validate_password(p1, User(email=d.get("email", ""), first_name=d.get("first_name", ""),
                                           last_name=d.get("last_name", "")))
            except forms.ValidationError as e:
                self.add_error("password1", e)
        return d


class ConnexionForm(AuthenticationForm):
    error_messages = {**AuthenticationForm.error_messages,
                      "invalid_login": "Identifiant (ou e-mail) ou mot de passe incorrect. "
                                       "Attention aux majuscules du mot de passe."}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["username"].label = "Identifiant ou e-mail"


class MotDePasseOublieForm(PasswordResetForm):
    """Réinitialisation : inclut les comptes invités qui n'ont pas encore choisi de mot de passe
    (sinon un apprenant dont l'invitation a expiré ne recevrait jamais rien) et force les liens https
    en production, même derrière un proxy qui masque le protocole."""

    def get_users(self, email):
        comptes = [u for u in User._default_manager.filter(email__iexact=email, is_active=True)
                   if u.email.casefold() == email.casefold()]
        if not comptes:
            logger.info("Mot de passe oublié : aucun compte actif pour %s", email)
        self.nb_comptes = len(comptes)
        return comptes

    def send_mail(self, subject_template_name, email_template_name, context, from_email, to_email,
                  html_email_template_name=None):
        """Comme Django, sans avaler l'échec en silence : il est journalisé et compté (self.echecs)."""
        from django.core.mail import EmailMultiAlternatives
        from django.template import loader
        sujet = "".join(loader.render_to_string(subject_template_name, context).splitlines())
        message = EmailMultiAlternatives(sujet, loader.render_to_string(email_template_name, context),
                                         from_email, [to_email])
        try:
            message.send()
            logger.info("Mot de passe oublié : lien envoyé à %s (%s)", to_email, context["user"].username)
        except Exception:
            self.echecs = getattr(self, "echecs", 0) + 1
            logger.exception("Mot de passe oublié : ÉCHEC d'envoi à %s — vérifier la configuration e-mail "
                             "(python manage.py tester_email %s)", to_email, to_email)

    def save(self, *a, use_https=False, extra_email_context=None, **kw):
        from apps.core.models import Parametres
        p = Parametres.charger()
        contexte = {"site_nom": f"{p.nom_plateforme} {p.suffixe}".strip(),
                    "jours": settings.PASSWORD_RESET_TIMEOUT // 86400, **(extra_email_context or {})}
        return super().save(*a, use_https=use_https or not settings.DEBUG, extra_email_context=contexte, **kw)
