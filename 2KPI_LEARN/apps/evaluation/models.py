from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from apps.core.stockage import stockage_prive
from apps.formation.models import (Competence, CritereEvaluation, Formation, Module, ObjectifSeance,
                                   PrerequisFormation, Seance)


class Inscription(models.Model):
    """Parcours d'un apprenant dans une promotion. Son statut ne change que par agenda/workflow.py :
    admise → confirmée (paiement) → en cours (démarrage de la promotion) → validée / non validée (clôture)."""
    class Statut(models.TextChoices):
        ADMISE = "admise", "Admise (à confirmer)"
        CONFIRMEE = "confirmee", "Confirmée"
        EN_COURS = "en_cours", "En cours"
        VALIDEE = "validee", "Validée"
        NON_VALIDEE = "non_validee", "Non validée"
        ABANDON = "abandon", "Abandon"

    class Paiement(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        RECU = "recu", "Reçu"
        EXONERE = "exonere", "Exonéré"

    # Statuts qui donnent accès aux contenus (sous réserve de l'ouverture des modules)
    STATUTS_ACTIFS = (Statut.CONFIRMEE, Statut.EN_COURS)

    apprenant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name="inscriptions")
    formation = models.ForeignKey(Formation, on_delete=models.CASCADE, related_name="inscriptions")
    promotion = models.ForeignKey("agenda.Promotion", on_delete=models.SET_NULL, null=True,
                                  blank=True, related_name="inscriptions")
    date_debut = models.DateField(null=True, blank=True)
    date_fin_prevue = models.DateField(null=True, blank=True)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.ADMISE)
    paiement = models.CharField(max_length=10, choices=Paiement.choices, default=Paiement.EN_ATTENTE)
    # Résultat figé à la clôture de la promotion
    taux_assiduite = models.PositiveSmallIntegerField("Assiduité (%)", null=True, blank=True)
    note_finale = models.DecimalField("Note finale (/20)", max_digits=4, decimal_places=2, null=True, blank=True)

    @property
    def est_active(self):
        return self.statut in self.STATUTS_ACTIFS

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


class AutoEvaluation(models.Model):
    """Position de l'apprenant sur un objectif de séance. Le premier niveau déclaré est conservé
    (niveau_initial) pour mesurer la progression ; l'apprenant peut se réévaluer autant qu'il veut."""
    class Niveau(models.IntegerChoices):
        PAS_ENCORE = 1, "Pas encore"
        AVEC_AIDE = 2, "Avec de l'aide"
        AUTONOME = 3, "En autonomie"
        EXPERT = 4, "Je peux l'expliquer"

    AIDE = {1: "Je ne sais pas encore le faire.", 2: "J'y arrive en m'aidant des supports ou d'une personne.",
            3: "Je sais le faire seul(e).", 4: "Je maîtrise au point de l'expliquer à quelqu'un d'autre."}
    SEUIL_ACQUIS = 3  # « En autonomie » et au-delà : objectif atteint

    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name="autoevaluations")
    objectif = models.ForeignKey(ObjectifSeance, on_delete=models.CASCADE, related_name="autoevaluations")
    niveau = models.PositiveSmallIntegerField(choices=Niveau.choices)
    niveau_initial = models.PositiveSmallIntegerField(choices=Niveau.choices)
    commentaire = models.CharField("Ce qui me bloque / ce que j'ai compris", max_length=500, blank=True)
    besoin_aide = models.BooleanField("Je souhaite en reparler avec le formateur", default=False)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Auto-évaluation"
        verbose_name_plural = "Auto-évaluations"
        unique_together = ("inscription", "objectif")

    @property
    def acquis(self):
        return self.niveau >= self.SEUIL_ACQUIS

    @property
    def progression(self):
        return self.niveau - self.niveau_initial

    def __str__(self):
        return f"{self.inscription.apprenant} · {self.objectif} : {self.niveau}/4"


class JournalStatut(models.Model):
    """Trace de chaque changement de statut d'une promotion ou d'une inscription (agenda/workflow.py)."""
    promotion = models.ForeignKey("agenda.Promotion", on_delete=models.CASCADE, null=True, blank=True,
                                  related_name="journal")
    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, null=True, blank=True,
                                    related_name="journal")
    de = models.CharField(max_length=12, blank=True)
    vers = models.CharField(max_length=12)
    motif = models.CharField(max_length=300, blank=True)
    par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                            related_name="+", help_text="Vide : changement automatique (tâche quotidienne, clôture).")
    le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Changement de statut"
        verbose_name_plural = "Journal des statuts"
        ordering = ["-le", "-id"]

    def __str__(self):
        return f"{self.inscription or self.promotion} : {self.de or '—'} → {self.vers}"


class PrerequisInscription(models.Model):
    """Où en est l'apprenant sur un prérequis de sa formation (absence de ligne = à faire)."""
    class Statut(models.TextChoices):
        OK = "ok", "OK"
        EN_COURS = "en_cours", "En cours"
        A_FAIRE = "a_faire", "À faire"

    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name="prerequis")
    prerequis = models.ForeignKey(PrerequisFormation, on_delete=models.CASCADE, related_name="etats")
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.A_FAIRE)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Prérequis d'un apprenant"
        verbose_name_plural = "Prérequis des apprenants"
        unique_together = ("inscription", "prerequis")

    def __str__(self):
        return f"{self.inscription.apprenant} · {self.prerequis} : {self.get_statut_display()}"


class NoteCritere(models.Model):
    """Note sur 20 d'un apprenant pour un critère de la grille d'évaluation de sa formation."""
    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name="notes_criteres")
    critere = models.ForeignKey(CritereEvaluation, on_delete=models.CASCADE, related_name="notes")
    note_sur_20 = models.DecimalField(max_digits=4, decimal_places=1,
                                      validators=[MinValueValidator(0), MaxValueValidator(20)])

    class Meta:
        verbose_name = "Note de critère"
        verbose_name_plural = "Notes de la grille d'évaluation"
        unique_together = ("inscription", "critere")

    def __str__(self):
        return f"{self.inscription.apprenant} · {self.critere.libelle} : {self.note_sur_20}"
