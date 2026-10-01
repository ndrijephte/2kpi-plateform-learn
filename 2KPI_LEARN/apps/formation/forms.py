from django import forms
from django.core.files.uploadedfile import UploadedFile
from apps.core.fichiers import type_depuis_nom, valider_fichier
from .models import Module, Ressource, Seance


class _SeanceChoix(forms.ModelChoiceField):
    def label_from_instance(self, s):
        return f"{s.module.code} · séance {s.ordre} — {s.theme or s.get_jour_display()}"


class _ModuleChoix(forms.ModelChoiceField):
    def label_from_instance(self, m):
        return f"{m.code} — {m.titre}"


class RessourceForm(forms.ModelForm):
    seance = _SeanceChoix(label="Séance", queryset=Seance.objects.none(), required=False)
    module = _ModuleChoix(label="… ou module entier", queryset=Module.objects.none(), required=False,
                          help_text="Choisis une séance OU un module (ressource commune à tout le module).")
    type = forms.ChoiceField(label="Type", required=False,
                             choices=[("", "Détection automatique")] + list(Ressource.Type.choices))

    class Meta:
        model = Ressource
        fields = ["titre", "seance", "module", "fichier", "url", "colab_url", "type", "instructions", "ordre"]
        widgets = {"instructions": forms.Textarea(attrs={"rows": 4, "placeholder":
                   "Ex. : 1) Télécharger l'archive  2) Décompresser dans data/  3) Ouvrir le notebook dans Colab"})}
        help_texts = {"fichier": "PDF, notebook, archive, données, présentation… (voir formats autorisés).",
                      "url": "Lien externe (site, vidéo, dépôt GitHub, jeu de données…).",
                      "ordre": "Position dans la liste (0 = en premier)."}

    def __init__(self, *a, formations=None, **kw):
        super().__init__(*a, **kw)
        self.fields["seance"].queryset = (Seance.objects.filter(module__formation__in=formations)
                                          .select_related("module").order_by("module__ordre", "ordre"))
        self.fields["module"].queryset = Module.objects.filter(formation__in=formations).order_by("ordre")
        self.fields["type"].initial = self.instance.type if self.instance.pk else ""
        self.fields["ordre"].required = False

    def clean_ordre(self):
        return self.cleaned_data.get("ordre") or 0

    def clean_fichier(self):
        f = self.cleaned_data.get("fichier")
        if isinstance(f, UploadedFile):  # nouveau dépôt uniquement (pas le fichier déjà stocké)
            valider_fichier(f)
        return f

    def clean(self):
        d = super().clean()
        if bool(d.get("seance")) == bool(d.get("module")):
            raise forms.ValidationError("Rattache la ressource à une séance OU à un module (un seul des deux).")
        if not (d.get("fichier") or d.get("url") or d.get("colab_url")):
            raise forms.ValidationError("Ajoute un fichier, un lien ou un lien Colab.")
        return d

    def save(self, commit=True):
        r = super().save(commit=False)
        choisi = self.cleaned_data.get("type")
        if choisi:
            r.type = choisi
        elif r.fichier:
            r.type = type_depuis_nom(r.fichier.name)
        else:
            r.type = Ressource.Type.LIEN
        if commit:
            r.save()
        return r
