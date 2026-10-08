from django import forms
from django.contrib.auth import get_user_model
from apps.core.permissions import ADMIN, APPRENANT, FORMATEUR, promotions_visibles, role_de
from .models import Annonce

User = get_user_model()


class _Personne(forms.ModelMultipleChoiceField):
    def label_from_instance(self, u):
        return u.get_full_name() or u.username


class AnnonceForm(forms.ModelForm):
    """Envoi d'une notification. Admin : tout le monde. Formateur : apprenants de ses promotions."""
    destinataires = _Personne(label="Destinataires", queryset=User.objects.none(), required=False,
                              widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = Annonce
        fields = ["cible", "promotion", "destinataires", "titre", "message", "par_email"]
        widgets = {"message": forms.Textarea(attrs={"rows": 5}),
                   "cible": forms.RadioSelect}
        labels = {"cible": "Envoyer à", "promotion": "Promotion"}

    def __init__(self, *a, auteur, **kw):
        super().__init__(*a, **kw)
        self.auteur = auteur
        self.admin = role_de(auteur) == ADMIN
        promos = promotions_visibles(auteur).filter(active=True).order_by("-date_debut")
        self.fields["promotion"].queryset = promos
        if self.admin:
            personnes = User.objects.filter(is_active=True).exclude(pk=auteur.pk)
            self.fields["cible"].choices = list(Annonce.Cible.choices)  # sans option vide
        else:  # formateur : uniquement les apprenants de ses promotions
            personnes = User.objects.filter(is_active=True, inscriptions__promotion__in=promos).distinct()
            Cible = Annonce.Cible
            self.fields["cible"].choices = [(Cible.PROMOTION, Cible.PROMOTION.label),
                                            (Cible.PERSONNES, "Des apprenants choisis")]
        self.fields["destinataires"].queryset = personnes.select_related("profil").order_by(
            "first_name", "last_name", "username")
        self.fields["cible"].initial = Annonce.Cible.PROMOTION

    def clean(self):
        d = super().clean()
        cible = d.get("cible")
        actifs = User.objects.filter(is_active=True).exclude(pk=self.auteur.pk)
        if cible == Annonce.Cible.PROMOTION:
            if not d.get("promotion"):
                self.add_error("promotion", "Choisis la promotion.")
                return d
            liste = actifs.filter(inscriptions__promotion=d["promotion"]).distinct()
        elif cible == Annonce.Cible.PERSONNES:
            liste = d.get("destinataires") or User.objects.none()
        elif cible == Annonce.Cible.APPRENANTS and self.admin:
            liste = actifs.filter(profil__role=APPRENANT)
        elif cible == Annonce.Cible.FORMATEURS and self.admin:
            liste = actifs.filter(profil__role=FORMATEUR)
        elif cible == Annonce.Cible.TOUS and self.admin:
            liste = actifs
        else:
            raise forms.ValidationError("Destinataires non autorisés.")
        self.liste_destinataires = list(liste)
        if not self.liste_destinataires:
            raise forms.ValidationError("Aucun destinataire ne correspond à ce choix.")
        return d


class FicheVitrineForm(forms.ModelForm):
    """Fiche publique d'une promotion sur le site vitrine (catalogue + formulaire d'inscription)."""
    code_vitrine = forms.CharField(
        label="Identifiant public", max_length=100, required=False,
        help_text="Utilisé dans l'adresse d'inscription (…/inscription.html?session=<b>identifiant</b>). "
                  "Vide = déduit du nom. Évite de le changer une fois la session annoncée.")

    class Meta:
        from .models import Promotion
        model = Promotion
        fields = ["publiee_vitrine", "code_vitrine", "domaine", "mode", "date_affichage", "horaire",
                  "duree", "lieu", "places_total", "places_hors_plateforme", "prix", "description_vitrine"]
        widgets = {"description_vitrine": forms.Textarea(attrs={"rows": 3, "maxlength": 400})}

    def clean_code_vitrine(self):
        from django.utils.text import slugify
        from .models import Promotion
        code = slugify(self.cleaned_data.get("code_vitrine") or "")[:100]
        if code and Promotion.objects.filter(code_vitrine=code, active=True).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Cet identifiant est déjà utilisé par une autre promotion active.")
        return code

    def clean(self):
        d = super().clean()
        total, ailleurs = d.get("places_total"), d.get("places_hors_plateforme")
        if total is not None and ailleurs is not None and ailleurs > total:
            self.add_error("places_hors_plateforme", "Ne peut pas dépasser le nombre total de places.")
        return d
