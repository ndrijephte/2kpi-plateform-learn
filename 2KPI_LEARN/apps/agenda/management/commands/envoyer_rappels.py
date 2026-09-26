"""Rappel automatique J-1 : notifie les apprenants des séances du lendemain.
À programmer via cron (une fois par jour). Idempotent (un rappel par événement/apprenant)."""
import datetime as dt
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.agenda.models import Evenement, Notification
from apps.agenda.services import apprenants_de, notifier


class Command(BaseCommand):
    help = "Envoie les rappels J-1 pour les séances du lendemain."

    def handle(self, *args, **options):
        demain = (timezone.localdate() + dt.timedelta(days=1))
        evenements = Evenement.objects.filter(
            date_debut__date=demain,
            statut__in=[Evenement.Statut.PLANIFIE, Evenement.Statut.CONFIRME],
        ).select_related("promotion")
        envoyes = 0
        for ev in evenements:
            for u in apprenants_de(ev.promotion):
                if Notification.objects.filter(evenement=ev, destinataire=u,
                                               type=Notification.Type.RAPPEL).exists():
                    continue
                heure = timezone.localtime(ev.date_debut).strftime("%H:%M")
                notifier([u], titre=f"Rappel : séance demain à {heure}",
                         message=f"{ev.libelle} — {ev.get_mode_display()}"
                                 + (f" · {ev.lieu}" if ev.lieu else ""),
                         evenement=ev, type=Notification.Type.RAPPEL)
                envoyes += 1
        self.stdout.write(self.style.SUCCESS(f"{envoyes} rappel(s) envoyé(s) pour le {demain}."))
