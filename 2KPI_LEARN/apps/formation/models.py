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
    class Jour(models.TextChoices):
        LUNDI = "lundi", "Lundi"
        MERCREDI = "mercredi", "Mercredi"
        VENDREDI = "vendredi", "Vendredi"
        SAMEDI = "samedi", "Samedi"

    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="seances")
    jour = models.CharField(max_length=10, choices=Jour.choices)
    theme = models.CharField(max_length=250, blank=True)
    duree_prevue_h = models.DecimalField(max_digits=4, decimal_places=1, default=1.5)
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Séance"
        verbose_name_plural = "Séances"
        ordering = ["module__ordre", "ordre"]

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
    class Type(models.TextChoices):
        PDF = "pdf", "PDF"
        NOTEBOOK = "notebook", "Notebook (.ipynb)"
        LIEN = "lien", "Lien"

    seance = models.ForeignKey(Seance, on_delete=models.CASCADE, related_name="ressources",
                               null=True, blank=True)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="ressources",
                               null=True, blank=True)
    titre = models.CharField(max_length=250)
    type = models.CharField(max_length=12, choices=Type.choices, default=Type.LIEN)
    fichier = models.FileField(upload_to="ressources/", blank=True, null=True)
    url = models.URLField(blank=True)
    colab_url = models.URLField("Lien Google Colab", blank=True)

    class Meta:
        verbose_name = "Ressource"
        verbose_name_plural = "Ressources"

    def __str__(self):
        return self.titre
