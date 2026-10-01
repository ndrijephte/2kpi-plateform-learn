from django.conf import settings
from django.db import models
from apps.formation.models import Formation, Seance


class Promotion(models.Model):
    """Une session/cohorte d'apprenants suivant une formation. Porte le calendrier."""
    formation = models.ForeignKey(Formation, on_delete=models.CASCADE, related_name="promotions")
    nom = models.CharField(max_length=200)
    date_debut = models.DateField(help_text="Date de la première semaine (le calendrier en découle).")
    formateur = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Formateur",
                                  on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="promotions_encadrees")
    active = models.BooleanField(default=True)
    ouverture_auto = models.BooleanField(
        "Ouverture automatique des modules", default=True,
        help_text="Chaque module s'ouvre le lundi de la semaine de sa première séance. "
                  "Sinon, le formateur ouvre les modules un à un.")

    class Meta:
        verbose_name = "Promotion"
        verbose_name_plural = "Promotions"
        ordering = ["-date_debut"]

    def __str__(self):
        return self.nom


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
        return f"{self.date_debut}{'→'+str(self.date_fin) if self.date_fin else ''} — {self.motif}"


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
            return self.seance.theme or f"{self.seance.module.code} — séance"
        return "Séance"

    @property
    def module_code(self):
        return self.seance.module.code if self.seance else ""

    def __str__(self):
        return f"{self.date_debut:%d/%m %H:%M} — {self.libelle}"


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
    lu = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-date_creation"]

    def __str__(self):
        return f"{self.titre} → {self.destinataire}"
