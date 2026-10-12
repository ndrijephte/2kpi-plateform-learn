from pathlib import Path
from urllib.parse import urlsplit
from django import forms
from django.core.files.uploadedfile import UploadedFile
from apps.core.fichiers import type_depuis_lien, type_depuis_nom, valider_fichier
from .models import Module, Ressource, Seance

CHOIX_TYPE = [("", "Détection automatique")] + list(Ressource.Type.choices)


class _SeanceChoix(forms.ModelChoiceField):
    def label_from_instance(self, s):
        return f"{s.module.code} · séance {s.ordre} — {s.theme or s.get_jour_display()}"


class _ModuleChoix(forms.ModelChoiceField):
    def label_from_instance(self, m):
        return f"{m.code} — {m.titre}"


class _CibleMixin:
    """Rattachement à une séance OU à un module des formations gérées."""

    def _init_cibles(self, formations):
        self.fields["seance"].queryset = (Seance.objects.filter(module__formation__in=formations)
                                          .select_related("module").order_by("module__ordre", "ordre"))
        self.fields["module"].queryset = Module.objects.filter(formation__in=formations).order_by("ordre")

    def _verifier_cible(self, d):
        if bool(d.get("seance")) == bool(d.get("module")):
            raise forms.ValidationError("Rattache la ressource à une séance OU à un module (un seul des deux).")


def _valider_depot(f):
    if isinstance(f, UploadedFile):  # nouveau dépôt uniquement (pas le fichier déjà stocké)
        valider_fichier(f)
    return f


def completer(r, type_choisi=""):
    """Type (choisi, sinon déduit du fichier puis du lien) et titre par défaut."""
    if type_choisi:
        r.type = type_choisi
    elif r.fichier:
        r.type = type_depuis_nom(r.fichier.name)
    else:
        r.type = type_depuis_lien(r.url or r.colab_url)
    if not r.titre:
        if r.fichier:
            r.titre = Path(r.fichier.name).stem.replace("_", " ").replace("-", " ").strip()[:250]
        elif r.type == Ressource.Type.VISIO:
            r.titre = "Classe virtuelle"
        else:
            r.titre = (urlsplit(r.url or r.colab_url).hostname or "Lien").removeprefix("www.")
    return r


class RessourceForm(_CibleMixin, forms.ModelForm):
    """Modification d'une ressource existante."""
    seance = _SeanceChoix(label="Séance", queryset=Seance.objects.none(), required=False)
    module = _ModuleChoix(label="… ou module entier", queryset=Module.objects.none(), required=False,
                          help_text="Choisis une séance OU un module (ressource commune à tout le module).")
    type = forms.ChoiceField(label="Type", required=False, choices=CHOIX_TYPE)

    class Meta:
        model = Ressource
        fields = ["titre", "seance", "module", "fichier", "url", "colab_url", "type", "instructions", "ordre"]
        widgets = {"instructions": forms.Textarea(attrs={"rows": 4, "placeholder":
                   "Ex. : 1) Télécharger l'archive  2) Décompresser dans data/  3) Ouvrir le notebook dans Colab"})}
        help_texts = {"fichier": "PDF, notebook, archive, données, présentation… (voir formats autorisés).",
                      "url": "Lien externe : classe virtuelle (Meet, Zoom, Teams), vidéo, dépôt GitHub, données…",
                      "ordre": "Position dans la liste (0 = en premier)."}

    def __init__(self, *a, formations=None, **kw):
        super().__init__(*a, **kw)
        self._init_cibles(formations)
        self.fields["type"].initial = self.instance.type if self.instance.pk else ""
        self.fields["ordre"].required = False
        self.fields["titre"].required = False

    def clean_ordre(self):
        return self.cleaned_data.get("ordre") or 0

    def clean_fichier(self):
        return _valider_depot(self.cleaned_data.get("fichier"))

    def clean(self):
        d = super().clean()
        self._verifier_cible(d)
        if not (d.get("fichier") or d.get("url") or d.get("colab_url")):
            raise forms.ValidationError("Ajoute un fichier, un lien ou un lien Colab.")
        return d

    def save(self, commit=True):
        r = completer(super().save(commit=False), self.cleaned_data.get("type"))
        if commit:
            r.save()
        return r


class CibleForm(_CibleMixin, forms.Form):
    """Ajout groupé : séance ou module qui recevra tous les documents."""
    seance = _SeanceChoix(label="Séance", queryset=Seance.objects.none(), required=False)
    module = _ModuleChoix(label="… ou module entier", queryset=Module.objects.none(), required=False,
                          help_text="Documents communs à toutes les séances du module.")

    def __init__(self, *a, formations=None, **kw):
        super().__init__(*a, **kw)
        self._init_cibles(formations)

    def clean(self):
        d = super().clean()
        self._verifier_cible(d)
        return d


class DocumentForm(forms.ModelForm):
    """Une ligne de l'ajout groupé : un fichier et/ou un lien, avec sa description."""
    type = forms.ChoiceField(label="Type", required=False, choices=CHOIX_TYPE)
    url = forms.URLField(label="Lien", required=False, assume_scheme="https",
                         widget=forms.URLInput(attrs={"placeholder": "https://meet.google.com/abc-defg-hij"}),
                         help_text="Classe virtuelle (Meet, Zoom, Teams), Colab, vidéo, dépôt GitHub…")

    class Meta:
        model = Ressource
        fields = ["titre", "type", "fichier", "url", "instructions"]
        labels = {"titre": "Titre", "fichier": "Fichier", "instructions": "Description"}
        help_texts = {"instructions": ""}
        widgets = {"titre": forms.TextInput(attrs={"placeholder": "Laisser vide = nom du fichier"}),
                   "instructions": forms.Textarea(attrs={"rows": 3, "placeholder":
                   "Ex. : Support de cours à lire avant la séance · Notebook du TP, à ouvrir dans Colab · "
                   "Lien de la classe virtuelle, ouvert 10 min avant le début"})}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["titre"].required = False

    def clean_fichier(self):
        return _valider_depot(self.cleaned_data.get("fichier"))

    def clean(self):
        d = super().clean()
        if not (d.get("fichier") or d.get("url")):
            raise forms.ValidationError("Ajoute un fichier ou un lien pour ce document.")
        return d

    def save(self, commit=True):
        r = super().save(commit=False)
        # Notebook + lien Colab sur la même ligne : le lien devient le bouton « Ouvrir dans Colab »
        if r.url and type_depuis_lien(r.url) == "notebook":
            r.colab_url, r.url = r.url, ""
        completer(r, self.cleaned_data.get("type"))
        if commit:
            r.save()
        return r


DocumentsFormSet = forms.modelformset_factory(Ressource, form=DocumentForm, extra=1, max_num=20,
                                              validate_max=True, can_delete=False)
