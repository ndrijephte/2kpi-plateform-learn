from django.conf import settings
from django.db import models
from django.urls import reverse
from apps.formation.models import Formation, Module, Seance


class Promotion(models.Model):
    """Une session/cohorte d'apprenants suivant une formation. Porte le calendrier.
    Son statut ne change que par agenda/workflow.py (conditions vérifiées, changement journalisé)."""
    class Statut(models.TextChoices):
        PLANIFIEE = "planifiee", "Planifiée"
        INSCRIPTIONS = "inscriptions", "Inscriptions ouvertes"
        PRETE = "prete", "Prête à démarrer"
        EN_COURS = "en_cours", "En cours"
        CLOTUREE = "cloturee", "Clôturée"
        ARCHIVEE = "archivee", "Archivée"

    # Statuts où la session est annoncée sur la vitrine et accepte des candidatures
    STATUTS_PUBLIABLES = (Statut.INSCRIPTIONS, Statut.PRETE)
    # Statuts où l'administration peut admettre ou confirmer un apprenant
    STATUTS_ADMISSION = (Statut.INSCRIPTIONS, Statut.PRETE, Statut.EN_COURS)

    formation = models.ForeignKey(Formation, on_delete=models.CASCADE, related_name="promotions")
    nom = models.CharField(max_length=200)
    date_debut = models.DateField(help_text="Date de la première semaine (le calendrier en découle).")
    formateur = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Formateur référent",
                                  on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="promotions_encadrees",
                                  help_text="Pilote la promotion et intervient sur tous ses modules. "
                                            "D'autres formateurs s'ajoutent module par module (Affectations).")
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.PLANIFIEE, editable=False)
    active = models.BooleanField(default=True, editable=False, help_text="Déduit du statut : faux une fois archivée.")
    effectif_minimum = models.PositiveSmallIntegerField(
        "Effectif minimum", default=1,
        help_text="Inscriptions confirmées nécessaires pour déclarer la promotion prête à démarrer.")
    code_vitrine = models.SlugField(
        "Code session (site vitrine)", max_length=100, blank=True,
        help_text="Identifiant de la session sur le site vitrine (ex. teledetection-sig-initiation) : "
                  "les candidatures reçues pour cette session sont rattachées à cette promotion.")

    # --- Fiche publique sur le site vitrine (API /api/sessions/) ---
    Domaine = Formation.Domaine  # mêmes valeurs que le catalogue
    Mode = Formation.Mode

    publiee_vitrine = models.BooleanField(
        "Publiée sur le site vitrine", default=False,
        help_text="Affichée dans le catalogue des sessions de 2kpinnov.org, ouverte aux inscriptions.")
    domaine = models.CharField(max_length=20, choices=Domaine.choices, default=Domaine.SOCLE,
                               help_text="Sert au filtre du catalogue.")
    mode = models.CharField(max_length=12, choices=Mode.choices, default=Mode.EN_LIGNE)
    date_affichage = models.CharField(
        "Date affichée", max_length=60, blank=True,
        help_text="Ex. « Tous les samedis ». Vide = la date de début (ex. « 14 octobre 2026 »).")
    horaire = models.CharField(max_length=60, blank=True, help_text="Ex. « 08h – 16h ».")
    duree = models.CharField("Durée", max_length=60, blank=True, help_text="Ex. « 5 jours », « 4 samedis ».")
    lieu = models.CharField(max_length=120, blank=True, help_text="Ex. « Abidjan, Cocody » ou « En ligne (visioconférence) ».")
    places_total = models.PositiveIntegerField("Places au total", default=20)
    places_hors_plateforme = models.PositiveIntegerField(
        "Places déjà attribuées hors plateforme", default=0,
        help_text="Inscrits reçus par e-mail, téléphone… Les inscrits de la plateforme sont comptés automatiquement.")
    prix = models.CharField(max_length=60, blank=True, help_text="Ex. « 150 000 FCFA ».")
    afficher_prix = models.BooleanField(
        "Afficher le prix sur le site vitrine", default=False,
        help_text="Décoché : le prix reste connu de l'administration mais n'apparaît pas sur le site.")
    description_vitrine = models.TextField(
        "Résumé (vitrine)", max_length=400, blank=True,
        help_text="Deux lignes affichées sur la carte. Vide = la description de la formation.")

    ouverture_auto = models.BooleanField(
        "Ouverture automatique des modules", default=True,
        help_text="Décision de l'administration : chaque module s'ouvre aux apprenants le lundi de la "
                  "semaine de sa première séance. Sinon, l'administration ouvre les modules un à un.")

    class Meta:
        verbose_name = "Promotion"
        verbose_name_plural = "Promotions"
        ordering = ["-date_debut"]

    def __str__(self):
        return self.nom

    @property
    def nb_inscrits_actifs(self):
        return self.inscriptions.exclude(statut="abandon").count()

    @property
    def places_restantes(self):
        """Places libres : total − inscrits de la plateforme (hors abandons) − places attribuées ailleurs."""
        return max(0, self.places_total - self.nb_inscrits_actifs - self.places_hors_plateforme)

    def save(self, *args, **kwargs):
        self.active = self.statut != self.Statut.ARCHIVEE
        if kwargs.get("update_fields") is not None and "statut" in kwargs["update_fields"]:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"active"}
        if self.publiee_vitrine and not self.code_vitrine:  # l'identifiant public est indispensable
            from django.utils.text import slugify
            base = slugify(self.nom)[:90] or "session"
            code, i = base, 1
            while Promotion.objects.filter(code_vitrine=code).exclude(pk=self.pk).exists():
                i += 1
                code = f"{base}-{i}"
            self.code_vitrine = code
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"code_vitrine"}
        super().save(*args, **kwargs)


class AccesModule(models.Model):
    """Décision d'ouverture d'un module pour une promotion (prime sur l'ouverture automatique)."""
    class Etat(models.TextChoices):
        AUTO = "auto", "Automatique (calendrier)"
        OUVERT = "ouvert", "Ouvert"
        FERME = "ferme", "Fermé"

    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name="acces_modules")
    module = models.ForeignKey("formation.Module", on_delete=models.CASCADE, related_name="acces")
    etat = models.CharField(max_length=8, choices=Etat.choices, default=Etat.AUTO)
    modifie_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Accès à un module"
        verbose_name_plural = "Accès aux modules"
        unique_together = ("promotion", "module")

    def __str__(self):
        return f"{self.module.code} · {self.promotion} : {self.get_etat_display()}"


class Affectation(models.Model):
    """Autorisation donnée par l'administration à un formateur d'intervenir dans une promotion,
    sur les modules cochés (ou sur tous). Sans affectation (ni rôle de référent), un formateur
    ne voit ni la promotion, ni sa formation, ni ses modules."""
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name="affectations")
    formateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="affectations")
    tous_les_modules = models.BooleanField("Tous les modules", default=False)
    modules = models.ManyToManyField("formation.Module", blank=True, related_name="affectations",
                                     help_text="Modules que ce formateur enseigne dans la promotion.")
    accordee_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="affectations_accordees")
    modifiee_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Affectation d'un formateur"
        verbose_name_plural = "Affectations des formateurs"
        unique_together = ("promotion", "formateur")

    def __str__(self):
        return f"{self.formateur} · {self.promotion}"


class Indisponibilite(models.Model):
    """Jour(s) non travaillé(s) évité(s) à la génération du calendrier."""
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name="indisponibilites",
                                  null=True, blank=True,
                                  help_text="Vide = s'applique à toutes les promotions.")
    date_debut = models.DateField()
    date_fin = models.DateField(null=True, blank=True, help_text="Vide = un seul jour.")
    motif = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "Indisponibilité (jour non travaillé)"
        verbose_name_plural = "Indisponibilités (jours non travaillés)"

    def couvre(self, d):
        fin = self.date_fin or self.date_debut
        return self.date_debut <= d <= fin

    def __str__(self):
        return f"{self.date_debut}{'→'+str(self.date_fin) if self.date_fin else ''} - {self.motif}"


class Evenement(models.Model):
    """Une séance datée (créneau) d'une promotion."""
    class Statut(models.TextChoices):
        PLANIFIE = "planifie", "Planifiée"
        CONFIRME = "confirme", "Confirmée"
        REALISE = "realise", "Réalisée"
        REPORTE = "reporte", "Reportée"
        ANNULE = "annule", "Annulée"

    class Mode(models.TextChoices):
        PRESENTIEL = "presentiel", "Présentiel"
        EN_LIGNE = "en_ligne", "En ligne"
        HYBRIDE = "hybride", "Hybride"

    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name="evenements")
    seance = models.ForeignKey(Seance, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="evenements")
    titre = models.CharField(max_length=250, blank=True,
                             help_text="Optionnel (sinon le thème de la séance).")
    date_debut = models.DateTimeField()
    duree_h = models.DecimalField(max_digits=4, decimal_places=1, default=1.5)
    lieu = models.CharField(max_length=200, blank=True)
    mode = models.CharField(max_length=12, choices=Mode.choices, default=Mode.EN_LIGNE)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.PLANIFIE)
    note = models.CharField(max_length=300, blank=True, help_text="Ex. motif d'un report.")

    class Meta:
        verbose_name = "Événement (séance datée)"
        verbose_name_plural = "Agenda (événements)"
        ordering = ["date_debut"]

    @property
    def libelle(self):
        if self.titre:
            return self.titre
        if self.seance:
            return self.seance.theme or f"{self.seance.module.code} - séance"
        return "Séance"

    @property
    def module_code(self):
        return self.seance.module.code if self.seance else ""

    def __str__(self):
        return f"{self.date_debut:%d/%m %H:%M} - {self.libelle}"


class Annonce(models.Model):
    """Message diffusé manuellement par un admin ou un formateur (une notification par destinataire)."""
    class Cible(models.TextChoices):
        TOUS = "tous", "Tous les utilisateurs"
        APPRENANTS = "apprenants", "Tous les apprenants"
        FORMATEURS = "formateurs", "Tous les formateurs"
        PROMOTION = "promotion", "Les apprenants d'une promotion"
        PERSONNES = "personnes", "Des personnes choisies"

    expediteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   related_name="annonces_envoyees")
    titre = models.CharField(max_length=200)
    message = models.TextField()
    cible = models.CharField(max_length=12, choices=Cible.choices)
    promotion = models.ForeignKey(Promotion, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="annonces")
    module = models.ForeignKey(Module, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
                               verbose_name="Module concerné",
                               help_text="Facultatif : un clic sur la notification ouvre ce module.")
    par_email = models.BooleanField("Envoyer aussi par e-mail", default=False)
    nb_destinataires = models.PositiveIntegerField(default=0)
    date_envoi = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notification envoyée"
        verbose_name_plural = "Notifications envoyées"
        ordering = ["-date_envoi"]

    def __str__(self):
        return self.titre


class Notification(models.Model):
    class Type(models.TextChoices):
        AGENDA = "agenda", "Agenda"
        RAPPEL = "rappel", "Rappel"
        INFO = "info", "Information"

    destinataire = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                     related_name="notifications")
    type = models.CharField(max_length=10, choices=Type.choices, default=Type.INFO)
    titre = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    evenement = models.ForeignKey(Evenement, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="notifications")
    expediteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="notifications_envoyees",
                                   help_text="Vide = message automatique de la plateforme.")
    annonce = models.ForeignKey(Annonce, on_delete=models.CASCADE, null=True, blank=True,
                                related_name="notifications")
    module = models.ForeignKey(Module, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
                               help_text="Module concerné (affiché avec la notification).")
    lien = models.CharField(max_length=300, blank=True,
                            help_text="Page ouverte au clic (chemin interne) ; à défaut, la séance ou le module.")
    lu = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-date_creation"]

    def __str__(self):
        return f"{self.titre} → {self.destinataire}"

    @property
    def destination(self):
        """Page ouverte au clic : lien explicite, sinon la séance de l'événement, sinon le module."""
        if self.lien.startswith("/") and not self.lien.startswith("//"):
            return self.lien
        if self.evenement_id and self.evenement.seance_id:
            return reverse("formation:seance", args=[self.evenement.seance_id])
        if self.module_id:
            return self.module.get_absolute_url()
        return ""

    @property
    def libelle_destination(self):
        if self.lien:
            return "Ouvrir"
        if self.evenement_id and self.evenement.seance_id:
            return "Voir la séance"
        return f"Ouvrir le module {self.module.code}" if self.module_id else ""
