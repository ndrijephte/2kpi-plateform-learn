"""Génération du calendrier d'une promotion + envoi de notifications."""
import datetime as dt
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone



def _indisponibilites(promotion):
    """Jours non travaillés propres à la promotion + ceux communs à toutes (promotion vide)."""
    from django.db.models import Q
    from .models import Indisponibilite
    return list(Indisponibilite.objects.filter(Q(promotion=promotion) | Q(promotion__isnull=True)))


def _creneau(promotion, seance, base_lundi, indispos):
    """Date/heure d'une séance pour une promotion, en évitant les jours non travaillés."""
    jour = base_lundi + dt.timedelta(weeks=seance.semaine_effective - 1, days=seance.jour)
    for _ in range(6):  # décalage d'une semaine, 6 essais max
        if any(i.couvre(jour) for i in indispos):
            jour += dt.timedelta(weeks=1)
        else:
            break
    naive = dt.datetime.combine(jour, seance.heure_debut)
    return timezone.make_aware(naive) if settings.USE_TZ else naive


def synchroniser_agenda(promotion):
    """Applique le paramétrage actuel des séances aux événements encore « planifiés »
    (les séances confirmées, réalisées, reportées ou annulées ne bougent pas),
    puis crée les événements des nouvelles séances. Retourne (recalés, créés)."""
    from .models import Evenement
    base_lundi = promotion.date_debut - dt.timedelta(days=promotion.date_debut.weekday())
    indispos = _indisponibilites(promotion)
    recales = 0
    for ev in (promotion.evenements.filter(statut=Evenement.Statut.PLANIFIE, seance__isnull=False)
               .select_related("seance__module")):
        s = ev.seance
        cible = _creneau(promotion, s, base_lundi, indispos)
        if (ev.date_debut, ev.duree_h, ev.mode, ev.lieu) != (cible, s.duree_prevue_h, s.mode, s.lieu):
            ev.date_debut, ev.duree_h, ev.mode, ev.lieu = cible, s.duree_prevue_h, s.mode, s.lieu
            ev.save(update_fields=["date_debut", "duree_h", "mode", "lieu"])
            recales += 1
    return recales, generer_agenda(promotion)


def generer_agenda(promotion):
    """Crée les événements manquants à partir du créneau paramétré de chaque séance
    (semaine, jour, heure, durée, mode, lieu). Semaine 1 = semaine contenant la date de début.
    Idempotent : ne recrée pas un événement déjà présent (par séance)."""
    from apps.formation.models import Seance
    from .models import Evenement

    base_lundi = promotion.date_debut - dt.timedelta(days=promotion.date_debut.weekday())
    indispos = _indisponibilites(promotion)
    crees = 0
    seances = Seance.objects.filter(module__formation=promotion.formation).select_related("module")
    deja = set(Evenement.objects.filter(promotion=promotion, seance__isnull=False)
               .values_list("seance_id", flat=True))
    for s in seances:
        if s.id in deja:
            continue
        Evenement.objects.create(
            promotion=promotion, seance=s,
            date_debut=_creneau(promotion, s, base_lundi, indispos),
            duree_h=s.duree_prevue_h, mode=s.mode, lieu=s.lieu,
        )
        crees += 1
    return crees


def apprenants_de(promotion):
    return [i.apprenant for i in promotion.inscriptions.select_related("apprenant")]


def notifier(destinataires, titre, message, evenement=None, type="info", envoyer_email=True,
             expediteur=None, annonce=None):
    """Crée une notification in-app pour chaque destinataire, + e-mail si possible.
    `expediteur` : admin/formateur à l'origine du message (None = message automatique)."""
    from .models import Notification
    crees = []
    for u in destinataires:
        crees.append(Notification.objects.create(
            destinataire=u, titre=titre, message=message, evenement=evenement, type=type,
            expediteur=expediteur, annonce=annonce))
        if envoyer_email and getattr(u, "email", ""):
            try:
                send_mail(titre, message, settings.DEFAULT_FROM_EMAIL, [u.email], fail_silently=True)
            except Exception:
                pass
    return crees
