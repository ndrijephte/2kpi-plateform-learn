"""Crée/actualise la formation GéoAI : 12 modules, 24 compétences (depuis le CSV),
48 séances (Lun/Mer/Ven/Sam). Idempotent."""
import csv
import re
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.formation.models import Formation, Module, Seance, Competence

MODULE_TITRES = {
    "M1": "Comprendre la GéoAI & sa chaîne de valeur",
    "M2": "Sentinel-2 sur Earth Engine (masquage nuages, médianes)",
    "M3": "Données climatiques (CHIRPS, ERA5-Land) & indices spectraux",
    "M4": "Cube spatio-temporel multi-bandes & séries mensuelles",
    "M5": "Normalisation, pondération & ACP",
    "M6": "Random Forest & validation croisée",
    "M7": "Clustering K-means & profils spatiaux",
    "M8": "Statistiques spatiales : Moran & Getis-Ord Gi*",
    "M9": "Projection de vulnérabilité & incertitude",
    "M10": "Système d'alerte : classification, anomalies, diffusion",
    "M11": "Cartographie QGIS : styles, mises en page, exports pro",
    "M12": "Automatisation, reproductibilité (Git) & documentation",
}

# Thèmes des séances de la semaine 1 (déjà rédigée) ; les autres modules
# reçoivent des séances vierges (thème à compléter au fil des manuels).
SEANCES_S1 = {
    "lundi": "Cadrage GéoAI (carte mentale)",
    "mercredi": "Installer Earth Engine & Python",
    "vendredi": "QGIS, Git & structure du projet",
    "samedi": "Atelier : chaîne Sentinel-2 de bout en bout",
}
JOURS = [("lundi", 1.5), ("mercredi", 1.5), ("vendredi", 1.5), ("samedi", 4.0)]

DATA = Path(__file__).resolve().parents[2] / "data" / "referentiel_competences_geoai.csv"


class Command(BaseCommand):
    help = "Initialise la formation GéoAI (modules, compétences, séances)."

    @transaction.atomic
    def handle(self, *args, **options):
        formation, _ = Formation.objects.get_or_create(
            slug="geoai-sassandra",
            defaults={"titre": "Formation GéoAI — Sassandra",
                      "description": "12 semaines, 48 séances, de la GéoAI aux systèmes d'alerte."},
        )

        # Modules
        modules = {}
        for i, (code, titre) in enumerate(MODULE_TITRES.items(), start=1):
            m, _ = Module.objects.update_or_create(
                formation=formation, code=code,
                defaults={"titre": titre, "ordre": i},
            )
            modules[code] = m

        # Compétences depuis le CSV
        nb_comp = 0
        if DATA.exists():
            with open(DATA, encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    code = (row.get("ID number") or "").strip()
                    if not re.match(r"^C\d+\.\d+$", code):
                        continue
                    parent = (row.get("Parent ID number") or "").strip()
                    module = modules.get(parent)
                    if not module:
                        continue
                    short = row.get("Shortname", "")
                    libelle = short.split(" — ", 1)[1] if " — " in short else short
                    mniv = re.search(r"niveau vis[ée]\s*:\s*(\d)", row.get("Description", ""))
                    niveau = int(mniv.group(1)) if mniv else 3
                    Competence.objects.update_or_create(
                        module=module, code=code,
                        defaults={"libelle": libelle.strip(), "niveau_vise": niveau},
                    )
                    nb_comp += 1

        # Séances (4 par module)
        nb_seances = 0
        for code, module in modules.items():
            for ordre, (jour, duree) in enumerate(JOURS, start=1):
                theme = SEANCES_S1.get(jour, "") if code == "M1" else ""
                Seance.objects.update_or_create(
                    module=module, jour=jour,
                    defaults={"theme": theme, "duree_prevue_h": duree, "ordre": ordre},
                )
                nb_seances += 1

        self.stdout.write(self.style.SUCCESS(
            f"OK — {len(modules)} modules, {nb_comp} compétences, {nb_seances} séances."))
