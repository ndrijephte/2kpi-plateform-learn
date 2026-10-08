"""Reprend les sessions écrites en dur dans le site vitrine (VITRINE_2KPI/js/sessions-data.js) en
promotions publiées : à lancer une fois lors du passage au catalogue synchronisé.

Idempotent : une session dont l'identifiant existe déjà comme code vitrine est ignorée.
    python manage.py importer_sessions_vitrine [--fichier CHEMIN] [--essai]
"""
import datetime as dt
import json
import re
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify
from apps.agenda.models import Promotion
from apps.formation.models import Formation

MOIS = {m: i for i, m in enumerate(["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
                                     "septembre", "octobre", "novembre", "décembre"], start=1)}


def lire_sessions(chemin):
    texte = Path(chemin).read_text(encoding="utf-8")
    m = re.search(r"var\s+SESSIONS\s*=\s*(\[.*?\n\]);", texte, re.S)
    if not m:
        raise CommandError(f"Tableau SESSIONS introuvable dans {chemin}")
    js = re.sub(r"^(\s*)([A-Za-z_]\w*)\s*:", r'\1"\2":', m.group(1), flags=re.M)  # clés entre guillemets
    js = re.sub(r",(\s*[}\]])", r"\1", js)  # virgules finales
    return json.loads(js)


def date_fr(texte):
    """« 10 août 2026 » → date ; autre chose (« Tous les samedis ») → None."""
    m = re.fullmatch(r"(\d{1,2})\s+([a-zéû]+)\s+(\d{4})", (texte or "").strip().lower())
    if m and m.group(2) in MOIS:
        return dt.date(int(m.group(3)), MOIS[m.group(2)], int(m.group(1)))
    return None


class Command(BaseCommand):
    help = "Importe les sessions du site vitrine (sessions-data.js) en promotions publiées."

    def add_arguments(self, parser):
        parser.add_argument("--fichier", default=str(Path(settings.BASE_DIR).parent / "VITRINE_2KPI/js/sessions-data.js"))
        parser.add_argument("--essai", action="store_true", help="Affiche ce qui serait créé, sans rien enregistrer.")

    @transaction.atomic
    def handle(self, *args, fichier, essai, **opts):
        crees = 0
        for s in lire_sessions(fichier):
            if Promotion.objects.filter(code_vitrine=s["id"]).exists():
                self.stdout.write(f"  = {s['id']} : déjà présente, ignorée")
                continue
            debut = date_fr(s.get("dateAffichage"))
            formation = Formation.objects.filter(slug=slugify(s["titre"])[:200]).first() or Formation(
                titre=s["titre"], description=s.get("description", ""))
            promo = Promotion(
                formation=formation, nom=s["titre"], date_debut=debut or dt.date.today(),
                active=True, publiee_vitrine=True, code_vitrine=s["id"],
                domaine=s.get("domaine") or Promotion.Domaine.SOCLE, mode=s.get("mode") or Promotion.Mode.EN_LIGNE,
                date_affichage="" if debut else s.get("dateAffichage", ""), horaire=s.get("horaire", ""),
                duree=s.get("duree", ""), lieu=s.get("lieu", ""), prix=s.get("prix", ""),
                places_total=s.get("placesTotal", 20),
                places_hors_plateforme=max(0, s.get("placesTotal", 20) - s.get("placesRestantes", 0)),
                description_vitrine=s.get("description", "")[:400])
            self.stdout.write(f"  + {s['id']} : « {promo.nom} » ({promo.date_affichage or promo.date_debut}, "
                              f"{s.get('placesRestantes')}/{promo.places_total} places)")
            if not essai:
                if not formation.pk:
                    formation.save()
                promo.formation = formation
                promo.save()
            crees += 1
        if essai:
            transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING(f"Essai : {crees} promotion(s) seraient créées (rien n'est enregistré)."))
        else:
            self.stdout.write(self.style.SUCCESS(f"{crees} promotion(s) créée(s) et publiée(s) sur la vitrine."))
