import datetime as dt
from decimal import Decimal
from pathlib import Path
from django.utils import timezone
from apps.core.stockage import stockage_prive
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

class Formation(models.Model):
    """Ce que 2KPI sait enseigner. Affichée au catalogue du site vitrine si l'administration le décide ;
    ses sessions (promotions) n'y deviennent réservables qu'une fois les inscriptions ouvertes."""
    class Domaine(models.TextChoices):
        SOCLE = "Socle", "Socle"
        URBANISME = "Urbanisme", "Urbanisme"
        DEMOGRAPHIE = "Démographie", "Démographie"
        PAYSAGER = "Paysager", "Paysager"
        NUMERIQUE = "Numérique", "Numérique"

    class Mode(models.TextChoices):
        EN_LIGNE = "En ligne", "En ligne"
        PRESENTIEL = "Présentiel", "Présentiel"
        HYBRIDE = "Hybride", "Hybride"

    titre = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    # Catalogue du site vitrine (API /api/catalogue/)
    catalogue = models.BooleanField("Afficher au catalogue du site", default=False,
                                    help_text="La formation apparaît sur 2kpinnov.org, avec « Être prévenu(e) » tant "
                                              "qu'aucune session n'est ouverte aux inscriptions.")
    domaine = models.CharField(max_length=20, choices=Domaine.choices, default=Domaine.SOCLE,
                               help_text="Sert au filtre du catalogue.")
    mode = models.CharField("Mode habituel", max_length=12, choices=Mode.choices, default=Mode.EN_LIGNE)
    duree_type = models.CharField("Durée habituelle", max_length=60, blank=True, help_text="Ex. « 5 jours », « 4 samedis ».")
    resume = models.CharField("Résumé (catalogue)", max_length=400, blank=True,
                              help_text="Deux lignes affichées sur le site. Vide = début de la description.")
    prix_indicatif = models.CharField("Prix indicatif", max_length=60, blank=True, help_text="Ex. « 150 000 FCFA ».")
    afficher_prix = models.BooleanField("Afficher le prix indicatif sur le site", default=False)
    # Règles de validation appliquées à la clôture d'une promotion (agenda/workflow.py)
    seuil_assiduite = models.PositiveSmallIntegerField(
        "Assiduité minimale (%)", default=80, validators=[MaxValueValidator(100)],
        help_text="Part des séances réalisées où l'apprenant était présent (ou en retard).")
    note_minimale = models.DecimalField("Note minimale (/20)", max_digits=4, decimal_places=1, default=Decimal("10"),
                                        validators=[MinValueValidator(0), MaxValueValidator(20)])
    # Composition de la note finale (en %, total 100) - voir tableau_bord/services.py
    poids_continu = models.PositiveSmallIntegerField(
        "Poids du contrôle continu (%)", default=40, validators=[MaxValueValidator(100)],
        help_text="Moyenne des livrables notés.")
    poids_projet = models.PositiveSmallIntegerField(
        "Poids du projet (%)", default=40, validators=[MaxValueValidator(100)],
        help_text="Grille d'évaluation de la formation (critères pondérés).")
    poids_soutenance = models.PositiveSmallIntegerField(
        "Poids de la soutenance (%)", default=20, validators=[MaxValueValidator(100)],
        help_text="0 = pas de soutenance.")

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
        return f"{self.code} - {self.titre}"

    def get_absolute_url(self):
        return f"{reverse('formation:module_detail', args=[self.code])}?formation={self.formation_id}"


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
        return f"{self.module.code} · {self.get_jour_display()} - {self.theme or 'Séance'}"


class ObjectifSeance(models.Model):
    """Objectif d'apprentissage d'une séance, formulé pour l'apprenant (« Je suis capable de… ») :
    c'est sur lui que porte l'auto-évaluation. Un objectif retiré alors que des apprenants s'y sont
    déjà évalués est archivé (actif=False) pour conserver leur historique."""
    seance = models.ForeignKey(Seance, on_delete=models.CASCADE, related_name="objectifs_seance")
    libelle = models.CharField("Objectif", max_length=300)
    ordre = models.PositiveIntegerField(default=0)
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Objectif de séance"
        verbose_name_plural = "Objectifs de séance"
        ordering = ["seance", "ordre", "id"]

    def __str__(self):
        return self.libelle


def definir_objectifs(seance, libelles):
    """Remplace les objectifs actifs de la séance par `libelles` (dans l'ordre), sans perdre les
    auto-évaluations : un libellé inchangé garde son objectif ; un libellé reformulé (texte proche)
    reprend l'objectif d'origine ; un objectif supprimé est archivé s'il a déjà des réponses,
    effacé sinon. Un libellé identique à un objectif archivé le réactive.
    Retourne les objectifs nouveaux pour les apprenants (créés ou réactivés)."""
    from difflib import SequenceMatcher
    libelles = list(dict.fromkeys(l.strip()[:300] for l in libelles if l.strip()))  # sans doublons
    existants = list(seance.objectifs_seance.all())
    libres = {o.libelle: o for o in existants}
    retenus = {}
    for i, lib in enumerate(libelles):
        if lib in libres:
            retenus[i] = libres.pop(lib)
    # Reformulations : appariement glouton des textes les plus proches (ratio ≥ 0,6)
    paires = sorted(((SequenceMatcher(None, lib.lower(), o.libelle.lower()).ratio(), i, o.libelle)
                     for i, lib in enumerate(libelles) if i not in retenus
                     for o in libres.values() if o.actif), reverse=True)
    for ratio, i, ancien in paires:
        if ratio >= 0.6 and i not in retenus and ancien in libres:
            retenus[i] = libres.pop(ancien)
    nouveaux = []
    for i, lib in enumerate(libelles):
        o = retenus.get(i) or ObjectifSeance(seance=seance)
        if not o.pk or not o.actif:
            nouveaux.append(o)
        o.libelle, o.ordre, o.actif = lib, i + 1, True
        o.save()
    for o in libres.values():  # retirés de la liste
        if o.autoevaluations.exists():
            if o.actif:
                o.actif = False
                o.save(update_fields=["actif"])
        else:
            o.delete()
    return nouveaux


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
        return f"{self.code} - {self.libelle}"


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
        VISIO = "visio", "Classe virtuelle (Meet, Zoom, Teams…)"
        LIEN = "lien", "Lien"
        AUTRE = "autre", "Autre fichier"

    seance = models.ForeignKey(Seance, on_delete=models.CASCADE, related_name="ressources",
                               null=True, blank=True)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="ressources",
                               null=True, blank=True)
    titre = models.CharField(max_length=250)
    type = models.CharField(max_length=12, choices=Type.choices, default=Type.LIEN)
    instructions = models.TextField("Description / consignes", blank=True,
                                    help_text="Ce que contient le document et comment l'utiliser.")
    fichier = models.FileField(upload_to="ressources/%Y/%m/", storage=stockage_prive, max_length=255,
                               blank=True, null=True)
    url = models.URLField("Lien", blank=True)
    colab_url = models.URLField("Lien Google Colab", blank=True)
    ordre = models.PositiveIntegerField(default=0)
    ajoute_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="ressources_deposees")
    date_ajout = models.DateTimeField(default=timezone.now)

    @property
    def est_visio(self):
        return self.type == self.Type.VISIO and bool(self.url)

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


class PrerequisFormation(models.Model):
    """Prérequis à remplir par l'apprenant avant ou pendant la formation (logiciel, compte, matériel…).
    Un prérequis obligatoire doit être « OK » pour que l'inscription soit confirmée."""
    formation = models.ForeignKey(Formation, on_delete=models.CASCADE, related_name="prerequis")
    libelle = models.CharField("Prérequis", max_length=200)
    obligatoire = models.BooleanField("Obligatoire avant confirmation", default=False)
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Prérequis de formation"
        verbose_name_plural = "Prérequis de formation"
        ordering = ["ordre", "id"]

    def __str__(self):
        return self.libelle


class CritereEvaluation(models.Model):
    """Critère de la grille d'évaluation du projet d'une formation, noté sur 20 et pondéré (%)."""
    formation = models.ForeignKey(Formation, on_delete=models.CASCADE, related_name="criteres")
    libelle = models.CharField("Critère", max_length=200)
    poids = models.PositiveSmallIntegerField("Poids (%)", validators=[MinValueValidator(1), MaxValueValidator(100)])
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Critère d'évaluation"
        verbose_name_plural = "Grille d'évaluation"
        ordering = ["ordre", "id"]

    def __str__(self):
        return f"{self.libelle} ({self.poids} %)"
