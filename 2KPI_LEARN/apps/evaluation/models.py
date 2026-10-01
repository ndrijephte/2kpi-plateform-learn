from decimal import Decimal
from django.conf import settings
from django.db import models
from apps.core.stockage import stockage_prive
from apps.formation.models import Formation, Module, Seance, Competence


class Inscription(models.Model):
    class Statut(models.TextChoices):
        EN_COURS = "en_cours", "En cours"
        TERMINEE = "terminee", "Terminée"
        ABANDON = "abandon", "Abandon"

    apprenant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name="inscriptions")
    formation = models.ForeignKey(Formation, on_delete=models.CASCADE, related_name="inscriptions")
    promotion = models.ForeignKey("agenda.Promotion", on_delete=models.SET_NULL, null=True,
                                  blank=True, related_name="inscriptions")
    date_debut = models.DateField(null=True, blank=True)
    date_fin_prevue = models.DateField(null=True, blank=True)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.EN_COURS)

    class Meta:
        verbose_name = "Inscription"
        verbose_name_plural = "Inscriptions"
        unique_together = ("apprenant", "formation")

    def __str__(self):
        return f"{self.apprenant} — {self.formation}"


class Presence(models.Model):
    class Statut(models.TextChoices):
        PRESENT = "present", "Présent"
        RETARD = "retard", "Retard"
        EXCUSE = "excuse", "Excusé"
        ABSENT = "absent", "Absent"

    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name="presences")
    seance = models.ForeignKey(Seance, on_delete=models.CASCADE, related_name="presences",
                               null=True, blank=True)
    evenement = models.ForeignKey("agenda.Evenement", on_delete=models.CASCADE,
                                  related_name="presences", null=True, blank=True)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.ABSENT)
    duree_realisee_h = models.DecimalField(max_digits=4, decimal_places=1, default=0)

    class Meta:
        verbose_name = "Présence"
        verbose_name_plural = "Présences"
        unique_together = ("inscription", "evenement")

    def __str__(self):
        return f"{self.inscription.apprenant} · {self.evenement} : {self.get_statut_display()}"


class Livrable(models.Model):
    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name="livrables")
    seance = models.ForeignKey(Seance, on_delete=models.CASCADE, related_name="livrables")
    rendu = models.BooleanField(default=False)
    note_sur_20 = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    fichier = models.FileField(upload_to="livrables/%Y/%m/", storage=stockage_prive, max_length=255,
                               blank=True, null=True)
    observations = models.TextField(blank=True)

    class Meta:
        verbose_name = "Livrable"
        verbose_name_plural = "Livrables"
        unique_together = ("inscription", "seance")

    def __str__(self):
        return f"Livrable {self.seance} — {self.inscription.apprenant}"


class Quiz(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="quiz")
    titre = models.CharField(max_length=200)
    bareme = models.PositiveIntegerField(default=20)

    class Meta:
        verbose_name = "Quiz"
        verbose_name_plural = "Quiz"

    def __str__(self):
        return self.titre


class Question(models.Model):
    class Type(models.TextChoices):
        QCM = "qcm", "Choix multiple"
        VF = "vf", "Vrai / Faux"
        COURT = "court", "Réponse courte"
        NUM = "num", "Numérique"
        APPARIEMENT = "appariement", "Appariement"

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    intitule = models.TextField()
    type = models.CharField(max_length=15, choices=Type.choices, default=Type.QCM)
    reponse_courte = models.CharField(max_length=200, blank=True)  # court / num
    categorie = models.CharField(max_length=120, blank=True)

    def __str__(self):
        return self.intitule[:70]


class Choix(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choix")
    texte = models.CharField(max_length=300)
    correct = models.BooleanField(default=False)
    poids = models.IntegerField(default=0)  # pour QCM à réponses multiples

    def __str__(self):
        return self.texte


class TentativeQuiz(models.Model):
    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name="tentatives")
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="tentatives")
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Tentative de quiz"
        verbose_name_plural = "Tentatives de quiz"

    def __str__(self):
        return f"{self.inscription.apprenant} · {self.quiz} : {self.score}"


class EvaluationCompetence(models.Model):
    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE,
                                    related_name="evaluations_competences")
    competence = models.ForeignKey(Competence, on_delete=models.CASCADE,
                                   related_name="evaluations")
    auto_eval = models.PositiveSmallIntegerField(null=True, blank=True)      # 1..4
    eval_formateur = models.PositiveSmallIntegerField(null=True, blank=True)  # 1..4
    valide = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Évaluation de compétence"
        verbose_name_plural = "Évaluations de compétences"
        unique_together = ("inscription", "competence")

    def __str__(self):
        return f"{self.competence.code} — {self.inscription.apprenant}"


class EvaluationProjet(models.Model):
    # Poids officiels de la grille (somme = 1.0)
    POIDS = {
        "acquisition": Decimal("0.20"),
        "modelisation": Decimal("0.25"),
        "stats_spatiales": Decimal("0.15"),
        "alerte": Decimal("0.20"),
        "cartographie": Decimal("0.10"),
        "reproductibilite": Decimal("0.10"),
    }
    inscription = models.OneToOneField(Inscription, on_delete=models.CASCADE,
                                       related_name="projet")
    acquisition = models.DecimalField("Acquisition & prétraitement", max_digits=4,
                                      decimal_places=1, null=True, blank=True)
    modelisation = models.DecimalField("Modélisation ML", max_digits=4,
                                       decimal_places=1, null=True, blank=True)
    stats_spatiales = models.DecimalField("Statistiques spatiales", max_digits=4,
                                          decimal_places=1, null=True, blank=True)
    alerte = models.DecimalField("Système d'alerte", max_digits=4,
                                 decimal_places=1, null=True, blank=True)
    cartographie = models.DecimalField("Cartographie & restitution", max_digits=4,
                                       decimal_places=1, null=True, blank=True)
    reproductibilite = models.DecimalField("Reproductibilité & documentation", max_digits=4,
                                           decimal_places=1, null=True, blank=True)

    class Meta:
        verbose_name = "Évaluation du projet"
        verbose_name_plural = "Évaluations de projet"

    @property
    def note_sur_20(self):
        total = Decimal("0")
        for critere, poids in self.POIDS.items():
            val = getattr(self, critere)
            if val is not None:
                total += Decimal(val) * poids
        return round(total, 2)

    def __str__(self):
        return f"Projet — {self.inscription.apprenant}"


class Soutenance(models.Model):
    inscription = models.OneToOneField(Inscription, on_delete=models.CASCADE,
                                       related_name="soutenance")
    note_sur_20 = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    date = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Soutenance"
        verbose_name_plural = "Soutenances"

    def __str__(self):
        return f"Soutenance — {self.inscription.apprenant}"
