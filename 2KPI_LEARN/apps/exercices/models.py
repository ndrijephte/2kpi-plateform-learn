"""Exercices composés par les formateurs : questions avec barème et correction, planifiés pour une
promotion entre une date d'ouverture et une date limite. L'apprenant répond (et peut modifier ses
réponses) jusqu'à la date limite ; il voit son résultat et la correction ensuite, une fois les
réponses rédigées corrigées par le formateur. Logique de notation : correction.py."""
from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from apps.formation.models import Module


class Exercice(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="exercices")
    titre = models.CharField(max_length=200)
    consignes = models.TextField("Consignes", blank=True, help_text="Affichées à l'apprenant avant les questions.")
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="exercices_crees")
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Exercice"
        verbose_name_plural = "Exercices"
        ordering = ["module__ordre", "titre"]

    def __str__(self):
        return f"{self.module.code} · {self.titre}"

    @property
    def bareme(self):
        return sum((q.points for q in self.questions.all()), Decimal(0))

    @property
    def verrouille(self):
        """Des apprenants ont répondu : questions, barème et réponses attendues sont figés."""
        return Reponse.objects.filter(copie__planification__exercice=self).exists()


class Question(models.Model):
    class Type(models.TextChoices):
        QCM = "qcm", "Choix multiple"
        VF = "vf", "Vrai / Faux"
        COURTE = "courte", "Réponse courte"
        NUMERIQUE = "numerique", "Valeur numérique"
        REDACTION = "redaction", "Réponse rédigée (corrigée par le formateur)"

    CORRIGEES_AUTOMATIQUEMENT = (Type.QCM, Type.VF, Type.COURTE, Type.NUMERIQUE)

    exercice = models.ForeignKey(Exercice, on_delete=models.CASCADE, related_name="questions")
    ordre = models.PositiveSmallIntegerField(default=0)
    type = models.CharField(max_length=10, choices=Type.choices, default=Type.QCM)
    enonce = models.TextField("Énoncé")
    points = models.DecimalField("Points", max_digits=5, decimal_places=2, default=Decimal(1),
                                 validators=[MinValueValidator(Decimal("0.25"))])
    correction = models.TextField("Correction", blank=True,
                                  help_text="Corrigé ou explication, montré à l'apprenant après la date limite.")
    reponses_acceptees = models.CharField(
        "Réponses acceptées", max_length=500, blank=True,
        help_text="Réponse courte : variantes séparées par « | » (casse, accents et espaces ignorés).")
    valeur_attendue = models.DecimalField("Valeur attendue", max_digits=14, decimal_places=4, null=True, blank=True)
    tolerance = models.DecimalField("Tolérance (±)", max_digits=14, decimal_places=4, default=Decimal(0),
                                    validators=[MinValueValidator(0)])

    class Meta:
        verbose_name = "Question d'exercice"
        verbose_name_plural = "Questions d'exercice"
        ordering = ["ordre", "id"]

    def __str__(self):
        from apps.core.texte_riche import en_texte
        return en_texte(self.enonce)[:70]

    @property
    def reponse_attendue(self):
        """Réponse attendue lisible (réponse courte ou valeur numérique), pour la correction."""
        def nombre(d):
            return f"{d.normalize():f}".replace(".", ",")
        if self.type == self.Type.COURTE:
            return " · ".join(a.strip() for a in self.reponses_acceptees.split("|") if a.strip())
        if self.type == self.Type.NUMERIQUE and self.valeur_attendue is not None:
            return nombre(self.valeur_attendue) + (f" ± {nombre(self.tolerance)}" if self.tolerance else "")
        return ""


class Choix(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choix")
    texte = models.CharField(max_length=300)
    correct = models.BooleanField("Bonne réponse", default=False)
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Choix proposé"
        verbose_name_plural = "Choix proposés"
        ordering = ["ordre", "id"]

    def __str__(self):
        return self.texte


class Planification(models.Model):
    """Un exercice donné à une promotion, avec sa fenêtre de travail."""
    exercice = models.ForeignKey(Exercice, on_delete=models.CASCADE, related_name="planifications")
    promotion = models.ForeignKey("agenda.Promotion", on_delete=models.CASCADE, related_name="exercices")
    ouverture = models.DateTimeField("Ouverture")
    date_limite = models.DateTimeField("Date limite")
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="+")

    class Meta:
        verbose_name = "Exercice planifié"
        verbose_name_plural = "Exercices planifiés"
        unique_together = ("exercice", "promotion")
        ordering = ["date_limite"]

    def __str__(self):
        return f"{self.exercice} · {self.promotion}"

    @property
    def a_venir(self):
        return timezone.now() < self.ouverture

    @property
    def ouvert(self):
        return self.ouverture <= timezone.now() < self.date_limite

    @property
    def termine(self):
        return timezone.now() >= self.date_limite


class Copie(models.Model):
    """Réponses d'un apprenant à un exercice planifié (modifiables jusqu'à la date limite)."""
    planification = models.ForeignKey(Planification, on_delete=models.CASCADE, related_name="copies")
    inscription = models.ForeignKey("evaluation.Inscription", on_delete=models.CASCADE, related_name="copies_exercices")
    enregistree_le = models.DateTimeField(auto_now=True)
    resultat_notifie = models.BooleanField(default=False, editable=False)

    class Meta:
        verbose_name = "Copie"
        verbose_name_plural = "Copies"
        unique_together = ("planification", "inscription")

    def __str__(self):
        return f"{self.inscription.apprenant} · {self.planification.exercice}"


class Reponse(models.Model):
    copie = models.ForeignKey(Copie, on_delete=models.CASCADE, related_name="reponses")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="reponses")
    valeur = models.TextField(blank=True, help_text="Texte saisi, ou identifiants des choix cochés séparés par des virgules.")
    points = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                 help_text="Vide : réponse rédigée en attente de correction.")
    commentaire = models.TextField("Commentaire du correcteur", blank=True)

    class Meta:
        verbose_name = "Réponse"
        verbose_name_plural = "Réponses"
        unique_together = ("copie", "question")
