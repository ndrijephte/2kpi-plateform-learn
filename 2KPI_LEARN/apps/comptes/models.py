from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models

class Profil(models.Model):
    class Role(models.TextChoices):
        APPRENANT = "apprenant", "Apprenant"
        FORMATEUR = "formateur", "Formateur"
        ADMIN = "admin", "Administrateur"

    utilisateur = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profil"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.APPRENANT)
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


class Prerequis(models.Model):
    class Statut(models.TextChoices):
        OK = "ok", "OK"
        EN_COURS = "en_cours", "En cours"
        A_FAIRE = "a_faire", "À faire"

    profil = models.OneToOneField(Profil, on_delete=models.CASCADE, related_name="prerequis")
    compte_gee = models.CharField("Compte Google Earth Engine validé", max_length=10,
                                  choices=Statut.choices, default=Statut.A_FAIRE)
    compte_github = models.CharField("Compte GitHub / GitLab créé", max_length=10,
                                     choices=Statut.choices, default=Statut.A_FAIRE)
    miniconda = models.CharField("Miniconda + JupyterLab installés", max_length=10,
                                 choices=Statut.choices, default=Statut.A_FAIRE)
    qgis = models.CharField("QGIS (version LTR) installé", max_length=10,
                            choices=Statut.choices, default=Statut.A_FAIRE)
    git = models.CharField("Git installé", max_length=10,
                           choices=Statut.choices, default=Statut.A_FAIRE)
    machine = models.CharField("Machine ≥ 8 Go RAM, connexion internet", max_length=10,
                               choices=Statut.choices, default=Statut.A_FAIRE)

    class Meta:
        verbose_name = "Prérequis"
        verbose_name_plural = "Prérequis"

    def __str__(self):
        return f"Prérequis de {self.profil}"
