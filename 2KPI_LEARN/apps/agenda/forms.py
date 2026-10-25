from django import forms
from django.contrib.auth import get_user_model
from apps.core.permissions import ADMIN, APPRENANT, FORMATEUR, modules_gerables, promotions_visibles, role_de
from apps.core.texte_riche import ChampRiche, EditeurRiche
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
        fields = ["cible", "promotion", "destinataires", "titre", "message", "module", "par_email"]
        field_classes = {"message": ChampRiche}
        widgets = {"cible": forms.RadioSelect, "message": EditeurRiche}
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
        self.fields["module"].queryset = (modules_gerables(auteur).select_related("formation")
                                          .order_by("formation__titre", "ordre"))
        self.fields["module"].label_from_instance = lambda m: f"{m.formation.titre} · {m.code} - {m.titre}"
        self.fields["module"].empty_label = "Aucun module en particulier"

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


def suggestion_nom(formation, date_debut):
    """Nom proposé pour une nouvelle session : « GéoAI - Session de mars 2027 »."""
    from django.utils.formats import date_format
    return f"{formation.titre} - Session de {date_format(date_debut, 'F Y')}" if formation and date_debut else ""


class SessionForm(forms.ModelForm):
    """Session (promotion) : création guidée et fiche publique sur le site vitrine.
    Les champs sont rangés par étape (ETAPES) ; les champs techniques sont dans « Options avancées »."""
    ETAPES = {
        "calendrier": ["formation", "date_debut", "nom", "formateur"],
        "fiche": ["mode", "date_affichage", "horaire", "duree", "lieu", "places_total", "prix", "afficher_prix",
                  "description_vitrine"],
        "avance": ["domaine", "code_vitrine", "places_hors_plateforme", "effectif_minimum"],
    }
    code_vitrine = forms.CharField(
        label="Identifiant public", max_length=100, required=False,
        help_text="Dans l'adresse d'inscription (…/inscription.html?session=<b>identifiant</b>). "
                  "Vide = déduit du nom. Évite de le changer une fois la session en ligne.")

    class Meta:
        from .models import Promotion
        model = Promotion
        fields = ["formation", "date_debut", "nom", "formateur", "mode", "date_affichage", "horaire", "duree",
                  "lieu", "places_total", "prix", "afficher_prix", "description_vitrine", "domaine", "code_vitrine",
                  "places_hors_plateforme", "effectif_minimum"]
        widgets = {"description_vitrine": forms.Textarea(attrs={"rows": 3, "maxlength": 400}),
                   "date_debut": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}
        labels = {"date_debut": "Date de début", "nom": "Nom de la session", "afficher_prix": "Afficher le prix sur le site",
                  "description_vitrine": "Résumé affiché sur le site"}
        help_texts = {"nom": "Nom interne et titre des messages aux apprenants. Proposé d'après la formation et la date.",
                      "formateur": "Pilote la session et intervient sur tous ses modules.",
                      "description_vitrine": "Deux lignes sur la carte du site. Vide = le résumé de la formation."}

    def __init__(self, *a, **kw):
        from apps.formation.models import Formation
        super().__init__(*a, **kw)
        self.creation = not self.instance.pk
        f = self.fields
        f["formateur"].queryset = (User.objects.filter(profil__role=FORMATEUR, is_active=True, is_superuser=False)
                                   .order_by("first_name", "last_name", "username"))
        f["formateur"].label_from_instance = lambda u: u.get_full_name() or u.username
        f["formateur"].empty_label = "— à choisir —"
        if self.creation:
            f["formation"].queryset = Formation.objects.filter(active=True).order_by("titre")
            f["formation"].empty_label = None
            f["nom"].required = False  # proposé automatiquement si laissé vide
            premiere = f["formation"].queryset.first()
            if premiere and not self.is_bound:  # valeurs habituelles de la formation, modifiables
                self.initial.update(self.valeurs_formation(premiere))
        else:
            del f["formation"]  # une session reste attachée à sa formation
            if self.instance.statut not in (self.instance.Statut.PLANIFIEE, self.instance.Statut.INSCRIPTIONS):
                del f["date_debut"]  # session prête ou démarrée : le calendrier se recale depuis le planning
            else:
                f["date_debut"].help_text = "Changer la date recale les séances encore « planifiées » du calendrier."

    @staticmethod
    def valeurs_formation(formation):
        return {"domaine": formation.domaine, "mode": formation.mode, "duree": formation.duree_type,
                "prix": formation.prix_indicatif, "afficher_prix": formation.afficher_prix}

    def etape(self, nom):
        return [self[c] for c in self.ETAPES[nom] if c in self.fields]

    def clean_code_vitrine(self):
        from django.utils.text import slugify
        from .models import Promotion
        code = slugify(self.cleaned_data.get("code_vitrine") or "")[:100]
        if code and Promotion.objects.filter(code_vitrine=code, active=True).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Cet identifiant est déjà utilisé par une autre session active.")
        return code

    def clean(self):
        d = super().clean()
        total, ailleurs = d.get("places_total"), d.get("places_hors_plateforme")
        if total is not None and ailleurs is not None and ailleurs > total:
            self.add_error("places_hors_plateforme", "Ne peut pas dépasser le nombre total de places.")
        if self.creation and not d.get("nom"):
            d["nom"] = suggestion_nom(d.get("formation"), d.get("date_debut"))
            self.instance.nom = d["nom"]
        return d
