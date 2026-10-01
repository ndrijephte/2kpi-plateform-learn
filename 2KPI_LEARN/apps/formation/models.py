import datetime as dt
from pathlib import Path
from django.utils import timezone
from apps.core.stockage import stockage_prive
from django.conf import settings
from django.db import models
from django.utils.text import slugify

class Formation(models.Model):
    titre = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Formation"
        verbose_name_plural = "Formations"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.titre)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.titre


class Module(models.Model):
    formation = models.ForeignKey(Formation, on_delete=models.CASCADE, related_name="modules")
    code = models.CharField(max_length=10)  # M1..M12
    titre = models.CharField(max_length=250)
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Module"
        verbose_name_plural = "Modules"
        ordering = ["ordre"]
        unique_together = ("formation", "code")

    def __str__(self):
        return f"{self.code} — {self.titre}"


class Seance(models.Model):
    """Séance type d'un module ; son créneau (semaine, jour, heure) sert à dater l'agenda des promotions."""
    class Jour(models.IntegerChoices):
        LUNDI = 0, "Lundi"
        MARDI = 1, "Mardi"
        MERCREDI = 2, "Mercredi"
        JEUDI = 3, "Jeudi"
        VENDREDI = 4, "Vendredi"
        SAMEDI = 5, "Samedi"
        DIMANCHE = 6, "Dimanche"

    class Mode(models.TextChoices):
        PRESENTIEL = "presentiel", "Présentiel"
        EN_LIGNE = "en_ligne", "En ligne"
        HYBRIDE = "hybride", "Hybride"

    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="seances")
    theme = models.CharField("Titre / thème", max_length=250, blank=True)
    objectifs = models.TextField("Objectifs & déroulé", blank=True)
    semaine = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Semaine de la formation (1 = semaine de démarrage). Vide = numéro d'ordre du module.")
    jour = models.PositiveSmallIntegerField(choices=Jour.choices, default=Jour.LUNDI)
    heure_debut = models.TimeField("Heure de début", default=dt.time(21, 30))
    duree_prevue_h = models.DecimalField("Durée (h)", max_digits=4, decimal_places=1, default=1.5)
    mode = models.CharField(max_length=12, choices=Mode.choices, default=Mode.EN_LIGNE)
    lieu = models.CharField(max_length=200, blank=True)
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Séance"
        verbose_name_plural = "Séances"
        ordering = ["module__ordre", "ordre"]

    @property
    def semaine_effective(self):
        return self.semaine or self.module.ordre or 1

    def __str__(self):
        return f"{self.module.code} · {self.get_jour_display()} — {self.theme or 'Séance'}"


class Competence(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="competences")
    code = models.CharField(max_length=15)  # C1.1..C12.2
    libelle = models.CharField(max_length=300)
    niveau_vise = models.PositiveSmallIntegerField(default=3)  # 1..4

    class Meta:
        verbose_name = "Compétence"
        verbose_name_plural = "Compétences"
        ordering = ["module__ordre", "code"]
        unique_together = ("module", "code")

    def __str__(self):
        return f"{self.code} — {self.libelle}"


class Ressource(models.Model):
    """Support pédagogique déposé par le formateur : fichier (tout format utile) ou lien, avec consignes."""
    class Type(models.TextChoices):
        PDF = "pdf", "PDF"
        NOTEBOOK = "notebook", "Notebook (.ipynb)"
        CODE = "code", "Script / code"
        ARCHIVE = "archive", "Archive (zip, rar…)"
        DOCUMENT = "document", "Document"
        PRESENTATION = "presentation", "Présentation"
        DONNEES = "donnees", "Données (CSV, SIG, raster…)"
        IMAGE = "image", "Image"
        VIDEO = "video", "Vidéo"
        LIEN = "lien", "Lien"
        AUTRE = "autre", "Autre fichier"

    seance = models.ForeignKey(Seance, on_delete=models.CASCADE, related_name="ressources",
                               null=True, blank=True)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="ressources",
                               null=True, blank=True)
    titre = models.CharField(max_length=250)
    type = models.CharField(max_length=12, choices=Type.choices, default=Type.LIEN)
    instructions = models.TextField("Consignes d'utilisation", blank=True,
                                    help_text="Ex. : « Décompresser puis ouvrir le projet QGIS ».")
    fichier = models.FileField(upload_to="ressources/%Y/%m/", storage=stockage_prive, max_length=255,
                               blank=True, null=True)
    url = models.URLField("Lien", blank=True)
    colab_url = models.URLField("Lien Google Colab", blank=True)
    ordre = models.PositiveIntegerField(default=0)
    ajoute_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="ressources_deposees")
    date_ajout = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Ressource"
        verbose_name_plural = "Ressources"
        ordering = ["ordre", "id"]

    @property
    def nom_fichier(self):
        return Path(self.fichier.name).name if self.fichier else ""

    @property
    def extension(self):
        return Path(self.fichier.name).suffix.lstrip(".").upper() if self.fichier else ""

    @property
    def taille(self):
        try:
            n = self.fichier.size if self.fichier else 0
        except OSError:
            return ""
        for unite in ("o", "Ko", "Mo", "Go"):
            if n < 1024:
                return f"{n:.0f} {unite}" if unite == "o" else f"{n:.1f} {unite}"
            n /= 1024
        return f"{n:.1f} To"

    def __str__(self):
        return self.titre
