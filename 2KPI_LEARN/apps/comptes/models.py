from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models

class Profil(models.Model):
    class Role(models.TextChoices):
        APPRENANT = "apprenant", "Apprenant"
        FORMATEUR = "formateur", "Formateur"
        ADMIN = "admin", "Administrateur"

    class Categorie(models.TextChoices):
        ETUDIANT = "etudiant", "Étudiant(e)"
        PROFESSIONNEL = "professionnel", "Professionnel(le)"

    utilisateur = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profil"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.APPRENANT)
    categorie = models.CharField("Profil", max_length=20, choices=Categorie.choices, blank=True,
                                 help_text="Renseigné par l'apprenant à la création de son compte.")
    structure = models.CharField("Structure / Université", max_length=200, blank=True)
    specialite = models.CharField("Spécialité", max_length=200, blank=True,
                                  default="Géomatique / Bases de données spatiales")
    telephone = models.CharField("Téléphone", max_length=40, blank=True)
    photo = models.FileField(upload_to="profils/", blank=True,
                             validators=[FileExtensionValidator(["png", "jpg", "jpeg", "webp"])])
    bio = models.TextField("Présentation", blank=True)

    class Meta:
        verbose_name = "Profil"
        verbose_name_plural = "Profils"

    def __str__(self):
        return f"{self.utilisateur.get_full_name() or self.utilisateur.username} ({self.get_role_display()})"

    @property
    def est_formateur(self):
        return self.role in (self.Role.FORMATEUR, self.Role.ADMIN)


class Candidature(models.Model):
    """Demande d'inscription reçue depuis le site vitrine, validée (ou non) par un admin."""
    class Statut(models.TextChoices):
        NOUVELLE = "nouvelle", "Nouvelle"
        ACCEPTEE = "acceptee", "Acceptée"
        REFUSEE = "refusee", "Refusée"

    nom_complet = models.CharField("Nom complet", max_length=200)
    email = models.EmailField()
    telephone = models.CharField("Téléphone", max_length=40)
    participants = models.PositiveSmallIntegerField(default=1)
    message = models.TextField(blank=True)
    session_code = models.CharField("Code session vitrine", max_length=100, blank=True)
    session_libelle = models.CharField("Session demandée", max_length=250, blank=True)
    promotion = models.ForeignKey("agenda.Promotion", on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="candidatures")
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.NOUVELLE)
    motif_refus = models.TextField("Motif du refus", blank=True)
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="candidatures")
    traitee_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="candidatures_traitees")
    traitee_le = models.DateTimeField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    date_reception = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Candidature"
        verbose_name_plural = "Candidatures"
        ordering = ["-date_reception"]

    def __str__(self):
        return f"{self.nom_complet} - {self.session_libelle or self.session_code}"


class Interet(models.Model):
    """« Être prévenu(e) de l'ouverture » : personne intéressée par une formation du catalogue qui n'a
    pas encore de session ouverte. Prévenue par e-mail dès que l'administration ouvre une session."""
    formation = models.ForeignKey("formation.Formation", on_delete=models.CASCADE, related_name="interets")
    nom_complet = models.CharField("Nom complet", max_length=200)
    email = models.EmailField()
    telephone = models.CharField("Téléphone", max_length=40)
    categorie = models.CharField("Profil", max_length=20, choices=Profil.Categorie.choices)
    structure = models.CharField("Structure / Université", max_length=200, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    prevenu_le = models.DateTimeField("Prévenu(e) de l'ouverture le", null=True, blank=True)
    promotion_annoncee = models.ForeignKey("agenda.Promotion", on_delete=models.SET_NULL, null=True, blank=True,
                                           related_name="+")
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = "Personne intéressée"
        verbose_name_plural = "Listes d'intérêt"
        ordering = ["-date"]

    def __str__(self):
        return f"{self.nom_complet} · {self.formation}"
