from django.core.cache import cache
from django.core.validators import FileExtensionValidator
from django.db import models

IMAGES = ["png", "jpg", "jpeg", "webp", "svg"]
EXTENSIONS_PAR_DEFAUT = (
    "pdf, ipynb, py, r, zip, rar, 7z, tar, gz, tgz, docx, doc, xlsx, xls, csv, pptx, ppt, "
    "odt, ods, odp, txt, md, json, geojson, kml, kmz, gpkg, shp, dbf, shx, prj, tif, tiff, "
    "png, jpg, jpeg, webp, qgz, qgs, mp4"
)


class Parametres(models.Model):
    """Paramétrage global de la plateforme (enregistrement unique, édité par l'admin)."""
    # Identité
    nom_plateforme = models.CharField("Nom", max_length=60, default="2KPI")
    suffixe = models.CharField("Suffixe (accent)", max_length=30, default="Learn", blank=True)
    logo = models.FileField("Logo", upload_to="parametres/", blank=True,
                            validators=[FileExtensionValidator(IMAGES)],
                            help_text="PNG, JPG, WEBP ou SVG, idéalement carré. Vide = pictogramme par défaut.")
    slogan = models.CharField("Signature (pied de page)", max_length=120,
                              default="Knowledge · Key · Planning · Innovation", blank=True)
    email_contact = models.EmailField("E-mail de contact", blank=True)
    # Page de connexion
    image_connexion = models.FileField("Image de fond", upload_to="parametres/", blank=True,
                                       validators=[FileExtensionValidator(["png", "jpg", "jpeg", "webp"])],
                                       help_text="Format paysage (≥ 1600 px de large). Vide = image par défaut.")
    titre_connexion = models.CharField("Titre", max_length=120,
                                       default="Apprends en pratiquant, progresse en continu.")
    texte_connexion = models.TextField("Texte d'accroche", default=(
        "La plateforme de formation pratique de 2KPI : cours, séances, quiz et suivi "
        "de progression au même endroit."))
    # Fichiers déposés (ressources, livrables)
    extensions_autorisees = models.TextField("Extensions autorisées", default=EXTENSIONS_PAR_DEFAUT,
                                             help_text="Séparées par des virgules, sans point.")
    taille_max_mo = models.PositiveIntegerField("Taille maximale (Mo)", default=100)

    class Meta:
        verbose_name = "Paramètres de la plateforme"
        verbose_name_plural = "Paramètres de la plateforme"

    CLE_CACHE = "core.parametres"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(self.CLE_CACHE)

    @classmethod
    def charger(cls):
        obj = cache.get(cls.CLE_CACHE)
        if obj is None:
            obj, _ = cls.objects.get_or_create(pk=1)
            cache.set(cls.CLE_CACHE, obj, 60)
        return obj

    @property
    def extensions(self):
        return sorted({e.strip().lower().lstrip(".") for e in self.extensions_autorisees.split(",") if e.strip()})

    def __str__(self):
        return "Paramètres de la plateforme"
