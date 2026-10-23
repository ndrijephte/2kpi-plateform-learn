"""Passages automatiques du workflow : démarre les promotions prêtes à leur date de début et
alerte l'administration de celles qui devaient démarrer sans être prêtes.
À programmer via cron (une fois par jour, tôt le matin). Idempotent."""
from django.core.management.base import BaseCommand
from apps.agenda.workflow import demarrages_du_jour


class Command(BaseCommand):
    help = "Démarre les promotions prêtes dont la date de début est atteinte ; signale les retards."

    def handle(self, *args, **options):
        demarrees, en_retard = demarrages_du_jour()
        for p in demarrees:
            self.stdout.write(f"  ▶ {p.nom} : démarrée")
        for p in en_retard:
            self.stdout.write(f"  ! {p.nom} : démarrage bloqué ({p.get_statut_display()})")
        self.stdout.write(self.style.SUCCESS(f"{len(demarrees)} promotion(s) démarrée(s), {len(en_retard)} en retard."))
