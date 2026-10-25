from django import forms
from django.forms import inlineformset_factory
from apps.core.texte_riche import ChampRiche, EditeurRiche
from .models import Choix, Exercice, Planification, Question


class ExerciceForm(forms.ModelForm):
    class Meta:
        model = Exercice
        fields = ["module", "titre", "consignes"]
        field_classes = {"consignes": ChampRiche}
        widgets = {"consignes": EditeurRiche}

    def __init__(self, *a, modules, **kw):
        super().__init__(*a, **kw)
        self.fields["module"].queryset = modules.select_related("formation").order_by("formation__titre", "ordre")
        self.fields["module"].label_from_instance = lambda m: f"{m.formation.titre} · {m.code} - {m.titre}"


class QuestionForm(forms.ModelForm):
    bonne_reponse_vf = forms.ChoiceField(label="Bonne réponse", choices=[("vrai", "Vrai"), ("faux", "Faux")],
                                         required=False, widget=forms.RadioSelect)

    class Meta:
        model = Question
        fields = ["type", "enonce", "points", "correction", "reponses_acceptees", "valeur_attendue", "tolerance", "ordre"]
        field_classes = {"enonce": ChampRiche, "correction": ChampRiche}
        widgets = {"enonce": EditeurRiche({"rows": 4}), "correction": EditeurRiche({"rows": 4})}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        q = self.instance
        if q.pk and q.type == Question.Type.VF:
            vrai = q.choix.filter(texte="Vrai").first()
            self.initial["bonne_reponse_vf"] = "vrai" if vrai and vrai.correct else "faux"

    def clean(self):
        d = super().clean()
        t = d.get("type")
        if t == Question.Type.VF and not d.get("bonne_reponse_vf"):
            self.add_error("bonne_reponse_vf", "Indique la bonne réponse.")
        if t == Question.Type.COURTE and not (d.get("reponses_acceptees") or "").strip(" |"):
            self.add_error("reponses_acceptees", "Indique au moins une réponse acceptée.")
        if t == Question.Type.NUMERIQUE and d.get("valeur_attendue") is None:
            self.add_error("valeur_attendue", "Indique la valeur attendue.")
        return d


class CorrectionSeuleForm(forms.ModelForm):
    """Exercice déjà commencé par des apprenants : seul le texte de correction reste modifiable."""
    class Meta:
        model = Question
        fields = ["correction"]
        field_classes = {"correction": ChampRiche}
        widgets = {"correction": EditeurRiche}


def choix_formset(question):
    """Propositions d'un QCM : lignes ajoutées et retirées à la volée dans la page (question.html) ;
    deux lignes vides pour commencer une question sans propositions."""
    extra = 0 if question.pk and question.choix.exists() else 2
    return inlineformset_factory(Question, Choix, fields=["texte", "correct"], extra=extra, can_delete=True,
                                 labels={"texte": "Proposition", "correct": "Bonne réponse"},
                                 widgets={"texte": forms.TextInput(attrs={"placeholder": "Saisis une proposition",
                                                                          "aria-label": "Proposition"}),
                                          "correct": forms.CheckboxInput(attrs={"aria-label": "Bonne réponse"})})


class PlanificationForm(forms.ModelForm):
    class Meta:
        model = Planification
        fields = ["promotion", "ouverture", "date_limite"]
        widgets = {"ouverture": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
                   "date_limite": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M")}

    def __init__(self, *a, promotions, **kw):
        super().__init__(*a, **kw)
        self.fields["promotion"].queryset = promotions
        for champ in ("ouverture", "date_limite"):
            self.fields[champ].input_formats = ["%Y-%m-%dT%H:%M"]

    def clean(self):
        d = super().clean()
        if d.get("ouverture") and d.get("date_limite") and d["date_limite"] <= d["ouverture"]:
            self.add_error("date_limite", "La date limite doit suivre l'ouverture.")
        promo, exercice = d.get("promotion"), self.instance.exercice
        if promo and Planification.objects.filter(exercice=exercice, promotion=promo).exclude(pk=self.instance.pk).exists():
            self.add_error("promotion", "Cet exercice est déjà planifié pour cette promotion.")
        return d
