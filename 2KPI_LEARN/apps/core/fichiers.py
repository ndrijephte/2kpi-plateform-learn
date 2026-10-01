"""Contrôle des fichiers déposés (ressources formateur, livrables apprenant)."""
from pathlib import Path
from django.core.exceptions import ValidationError
from .models import Parametres

# Jamais servis depuis /media : exécutables ou contenus interprétés par le navigateur.
INTERDITES = {"exe", "bat", "cmd", "sh", "ps1", "msi", "com", "scr", "js", "html", "htm",
              "svg", "php", "phtml", "jsp", "asp", "aspx", "cgi", "jar", "dll", "so"}

TYPES = {  # extension -> type de ressource
    "pdf": "pdf",
    "ipynb": "notebook", "py": "code", "r": "code",
    "zip": "archive", "rar": "archive", "7z": "archive", "tar": "archive", "gz": "archive", "tgz": "archive",
    "docx": "document", "doc": "document", "odt": "document", "txt": "document", "md": "document",
    "pptx": "presentation", "ppt": "presentation", "odp": "presentation",
    "xlsx": "donnees", "xls": "donnees", "csv": "donnees", "ods": "donnees", "json": "donnees",
    "geojson": "donnees", "kml": "donnees", "kmz": "donnees", "gpkg": "donnees", "shp": "donnees",
    "dbf": "donnees", "shx": "donnees", "prj": "donnees", "tif": "donnees", "tiff": "donnees",
    "qgz": "donnees", "qgs": "donnees",
    "png": "image", "jpg": "image", "jpeg": "image", "webp": "image",
    "mp4": "video",
}


def extension(nom):
    return Path(nom or "").suffix.lower().lstrip(".")


def type_depuis_nom(nom):
    return TYPES.get(extension(nom), "autre")


def valider_fichier(fichier):
    """Lève ValidationError si l'extension ou la taille ne respecte pas le paramétrage."""
    p = Parametres.charger()
    ext = extension(fichier.name)
    if not ext or ext in INTERDITES or ext not in p.extensions:
        raise ValidationError(
            f"Type de fichier « .{ext or '?'} » non autorisé. Formats acceptés : {', '.join(p.extensions)}.")
    if fichier.size > p.taille_max_mo * 1024 * 1024:
        raise ValidationError(f"Fichier trop volumineux (max {p.taille_max_mo} Mo).")
