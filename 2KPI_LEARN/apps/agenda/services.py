"""Génération du calendrier d'une promotion + envoi de notifications."""
import datetime as dt
from decimal import Decimal
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

# Rythme par défaut : jour de séance -> (jour_semaine 0=lundi, heure, durée par défaut)
RYTHME = {
    "lundi":    (0, dt.time(21, 30), Decimal("1.5")),
    "mercredi": (2, dt.time(21, 30), Decimal("1.5")),
    "vendredi": (4, dt.time(21, 30), Decimal("1.5")),
    "samedi":   (5, dt.time(8, 0),  Decimal("4.0")),
}


def _indisponible(promotion, d):
    from .models import Indisponibilite
    qs = Indisponibilite.objects.filter(promotion__in=[promotion, None])
    return any(i.couvre(d) for i in qs)


def generer_agenda(promotion):
    """Crée les événements manquants pour chaque séance de la formation.
    Idempotent : ne recrée pas un événement déjà présent (par séance)."""
    from apps.formation.models import Seance
    from .models import Evenement

    # Lundi de la semaine contenant la date de début
    base_lundi = promotion.date_debut - dt.timedelta(days=promotion.date_debut.weekday())
    crees = 0
    seances = Seance.objects.filter(module__formation=promotion.formation).select_related("module")
    for s in seances:
        if Evenement.objects.filter(promotion=promotion, seance=s).exists():
            continue
        rythme = RYTHME.get(s.jour)
        if not rythme:
            continue
        weekday, heure, duree_def = rythme
        semaine = base_lundi + dt.timedelta(weeks=max(0, (s.module.ordre or 1) - 1))
        jour = semaine + dt.timedelta(days=weekday)
        # éviter les jours non travaillés (décalage d'une semaine, max 6 essais)
        for _ in range(6):
            if _indisponible(promotion, jour):
                jour = jour + dt.timedelta(weeks=1)
            else:
                break
        naive = dt.datetime.combine(jour, heure)
        date_debut = timezone.make_aware(naive) if settings.USE_TZ else naive
        Evenement.objects.create(
            promotion=promotion, seance=s, date_debut=date_debut,
            duree_h=(s.duree_prevue_h or duree_def),
            mode=Evenement.Mode.EN_LIGNE if s.jour != "samedi" else Evenement.Mode.HYBRIDE,
        )
        crees += 1
    return crees


def apprenants_de(promotion):
    return [i.apprenant for i in promotion.inscriptions.select_related("apprenant")]


def notifier(destinataires, titre, message, evenement=None, type="info", envoyer_email=True):
    """Crée une notification in-app pour chaque destinataire, + e-mail si possible."""
    from .models import Notification
    crees = []
    for u in destinataires:
        crees.append(Notification.objects.create(
            destinataire=u, titre=titre, message=message, evenement=evenement, type=type))
        if envoyer_email and getattr(u, "email", ""):
            try:
                send_mail(titre, message, settings.DEFAULT_FROM_EMAIL, [u.email], fail_silently=True)
            except Exception:
                pass
    return crees
