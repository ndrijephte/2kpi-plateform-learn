"""Passages automatiques du workflow : démarre les promotions prêtes à leur date de début, alerte
l'administration de celles qui devaient démarrer sans être prêtes, relance les feuilles de présence
non enregistrées (formateurs à J+1, administrateurs à J+3).
À programmer via cron (une fois par jour, tôt le matin). Idempotent."""
from django.core.management.base import BaseCommand
from apps.agenda.workflow import demarrages_du_jour, relances_presences


class Command(BaseCommand):
    help = "Démarre les promotions prêtes à leur date, signale les retards, relance les présences non saisies."

    def handle(self, *args, **options):
        demarrees, en_retard = demarrages_du_jour()
        for p in demarrees:
            self.stdout.write(f"  ▶ {p.nom} : démarrée")
        for p in en_retard:
            self.stdout.write(f"  ! {p.nom} : démarrage bloqué ({p.get_statut_display()})")
        rappels, alertes = relances_presences()
        self.stdout.write(self.style.SUCCESS(f"{len(demarrees)} promotion(s) démarrée(s), {len(en_retard)} en retard ; "
                                             f"présences : {rappels} rappel(s) formateur, {alertes} alerte(s) admin."))
