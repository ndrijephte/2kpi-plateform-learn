from django import forms
from apps.agenda.models import Indisponibilite
from apps.formation.models import Competence, Formation, Module, Seance
from .models import Parametres

SECTIONS = {
    "identite": ("Identité & logo", ["nom_plateforme", "suffixe", "logo", "slogan", "email_contact"]),
    "connexion": ("Page de connexion", ["image_connexion", "titre_connexion", "texte_connexion"]),
    "fichiers": ("Fichiers déposés", ["extensions_autorisees", "taille_max_mo"]),
}


def parametres_form(section):
    champs = SECTIONS[section][1]

    class _Form(forms.ModelForm):
        class Meta:
            model = Parametres
            fields = champs
            widgets = {"texte_connexion": forms.Textarea(attrs={"rows": 3}),
                       "extensions_autorisees": forms.Textarea(attrs={"rows": 3})}
    return _Form


class FormationForm(forms.ModelForm):
    class Meta:
        model = Formation
        fields = ["titre", "slug", "description", "active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}
        help_texts = {"slug": "Identifiant d'URL ; laissé vide, il est déduit du titre."}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["slug"].required = False


class ModuleForm(forms.ModelForm):
    class Meta:
        model = Module
        fields = ["code", "titre", "ordre"]
        help_texts = {"ordre": "Sert aussi de semaine par défaut des séances du module."}

    def clean_code(self):  # unicité (formation, code) : la formation est fixée par la vue
        code = self.cleaned_data["code"].strip().upper()
        if Module.objects.filter(formation_id=self.instance.formation_id, code=code).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ce code existe déjà dans la formation.")
        return code


class SeanceForm(forms.ModelForm):
    class Meta:
        model = Seance
        fields = ["theme", "ordre", "semaine", "jour", "heure_debut", "duree_prevue_h", "mode", "lieu", "objectifs"]
        widgets = {"heure_debut": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
                   "objectifs": forms.Textarea(attrs={"rows": 4})}


class CompetenceForm(forms.ModelForm):
    class Meta:
        model = Competence
        fields = ["code", "libelle", "niveau_vise"]

    def clean_code(self):
        code = self.cleaned_data["code"].strip().upper()
        if Competence.objects.filter(module_id=self.instance.module_id, code=code).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ce code existe déjà dans le module.")
        return code

    def clean_niveau_vise(self):
        n = self.cleaned_data["niveau_vise"]
        if not 1 <= n <= 4:
            raise forms.ValidationError("Niveau entre 1 et 4.")
        return n


class IndisponibiliteForm(forms.ModelForm):
    class Meta:
        model = Indisponibilite
        fields = ["date_debut", "date_fin", "motif", "promotion"]
        widgets = {"date_debut": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                   "date_fin": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}
        labels = {"date_debut": "Du", "date_fin": "Au (optionnel)", "promotion": "Promotion (vide = toutes)"}

    def clean(self):
        d = super().clean()
        if d.get("date_fin") and d.get("date_debut") and d["date_fin"] < d["date_debut"]:
            self.add_error("date_fin", "La date de fin précède la date de début.")
        return d


# ---------- Quiz ----------
from django.forms import inlineformset_factory  # noqa: E402
from apps.evaluation.models import Choix, Question, Quiz  # noqa: E402


class _ModuleChoix(forms.ModelChoiceField):
    def label_from_instance(self, m):
        return f"{m.formation.titre} · {m.code} — {m.titre}"


class QuizForm(forms.ModelForm):
    module = _ModuleChoix(queryset=Module.objects.select_related("formation")
                          .order_by("formation__titre", "ordre"))

    class Meta:
        model = Quiz
        fields = ["module", "titre", "bareme"]
        labels = {"bareme": "Barème"}


AIDE_TYPES = {
    "qcm": "Coche la ou les bonnes réponses (plusieurs cochées = QCM à réponses multiples).",
    "vf": "Deux réponses « Vrai » et « Faux », une seule cochée comme correcte.",
    "court": "Réponses acceptées séparées par « | » (ex. : 8 | huit). Casse ignorée.",
    "num": "Valeur attendue, avec tolérance optionnelle : « 5000:1500 » accepte 3500 à 6500.",
    "appariement": "Une ligne par paire, au format « élément -> correspondance ».",
}


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ["intitule", "type", "reponse_courte", "categorie"]
        labels = {"intitule": "Énoncé", "reponse_courte": "Réponse attendue (réponse courte / numérique)",
                  "categorie": "Catégorie (optionnel)"}
        widgets = {"intitule": forms.Textarea(attrs={"rows": 3})}


ChoixFormSet = inlineformset_factory(
    Question, Choix, fields=["texte", "correct"], extra=4, can_delete=True,
    labels={"texte": "Réponse", "correct": "Correcte"})


def verifier_question(type_q, reponse, choix):
    """Cohérence question/réponses. `choix` = [(texte, correct)] non supprimés. Retourne des erreurs."""
    erreurs = []
    if type_q in ("qcm", "vf"):
        if len(choix) < 2:
            erreurs.append("Il faut au moins deux réponses proposées.")
        nb_ok = sum(1 for _, ok in choix if ok)
        if nb_ok == 0:
            erreurs.append("Coche au moins une réponse correcte.")
        if type_q == "vf" and (len(choix) != 2 or nb_ok != 1):
            erreurs.append("Vrai/Faux : exactement deux réponses dont une seule correcte.")
    elif type_q == "appariement":
        if len(choix) < 2:
            erreurs.append("Il faut au moins deux paires.")
        if any("->" not in t for t, _ in choix):
            erreurs.append("Chaque paire doit être au format « élément -> correspondance ».")
    elif type_q == "court":
        if not [a for a in reponse.split("|") if a.strip()]:
            erreurs.append("Indique au moins une réponse acceptée.")
    elif type_q == "num":
        try:
            [float(x.replace(",", ".")) for x in reponse.split(":")[:2]]
            if not reponse.strip():
                raise ValueError
        except ValueError:
            erreurs.append("Réponse numérique attendue, ex. « 12.5 » ou « 5000:1500 ».")
    return erreurs


class GiftForm(forms.Form):
    fichier = forms.FileField(label="Fichier GIFT (.gift ou .txt)")
    remplacer = forms.BooleanField(label="Remplacer les questions existantes", required=False)

    def clean_fichier(self):
        f = self.cleaned_data["fichier"]
        if not f.name.lower().endswith((".gift", ".txt")):
            raise forms.ValidationError("Format attendu : .gift ou .txt")
        if f.size > 2 * 1024 * 1024:
            raise forms.ValidationError("Fichier trop volumineux (2 Mo max).")
        try:
            self.texte = f.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            raise forms.ValidationError("Le fichier doit être encodé en UTF-8.")
        return f
