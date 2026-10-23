"""Droits et notifications des exercices.

- Composer un exercice : formateur du module (modules_gerables) ou administration.
- Le planifier, suivre et corriger les copies : promotions où le formateur intervient sur ce module.
- Le faire : apprenant à l'inscription confirmée ou en cours dans la promotion, après l'ouverture.
"""
from django.utils import timezone
from apps.agenda.models import Notification, Promotion
from apps.agenda.services import notifier
from apps.core.permissions import interventions, modules_gerables
from .correction import resultat
from .models import Copie, Planification


def exercices_gerables(user):
    from .models import Exercice
    return Exercice.objects.filter(module__in=modules_gerables(user))


def promotions_planifiables(user, exercice, actives_seulement=True):
    """Promotions de la formation de l'exercice où l'utilisateur intervient sur son module."""
    qs = Promotion.objects.filter(formation_id=exercice.module.formation_id)
    if actives_seulement:
        qs = qs.filter(active=True)
    perimetre = interventions(user)
    if perimetre is None:
        return qs
    return qs.filter(pk__in=[pid for pid, modules in perimetre.items()
                             if modules is None or exercice.module_id in modules])


def peut_suivre(user, planification):
    return promotions_planifiables(user, planification.exercice, actives_seulement=False) \
        .filter(pk=planification.promotion_id).exists()


def planifications_apprenant(inscription):
    """Exercices de la promotion de l'apprenant (déjà ouverts ou à venir)."""
    if inscription is None or not inscription.promotion_id:
        return Planification.objects.none()
    return (Planification.objects.filter(promotion_id=inscription.promotion_id)
            .select_related("exercice__module").order_by("date_limite"))


def annoncer(planification, par):
    from apps.agenda.services import inscriptions_a_pointer
    apprenants = [i.apprenant for i in inscriptions_a_pointer(planification.promotion).select_related("apprenant")]
    debut = timezone.localtime(planification.ouverture)
    fin = timezone.localtime(planification.date_limite)
    quand = (f"à faire avant le {fin:%d/%m à %H:%M}" if debut <= timezone.localtime() else
             f"ouvert du {debut:%d/%m à %H:%M} au {fin:%d/%m à %H:%M}")
    notifier(apprenants, titre=f"Nouvel exercice : {planification.exercice.titre}",
             message=f"{planification.exercice.module.code} - {quand}. Ton résultat et la correction seront "
                     "visibles après la date limite.", type=Notification.Type.INFO, expediteur=par)


def notifier_resultat(copie):
    """Prévient l'apprenant que son résultat est visible (une seule fois)."""
    planif = copie.planification
    if copie.resultat_notifie or not planif.termine or not resultat(planif, copie)["complet"]:
        return False
    r = resultat(planif, copie)
    notifier([copie.inscription.apprenant], titre=f"Résultat disponible : {planif.exercice.titre}",
             message=f"{r['points']:g} / {r['bareme']:g} points ({r['note_sur_20']}/20). Consulte la correction dans Exercices.",
             type=Notification.Type.INFO)
    copie.resultat_notifie = True
    copie.save(update_fields=["resultat_notifie"])
    return True


def notifier_resultats_du_jour():
    """Tâche quotidienne : résultats des exercices dont la date limite est passée et la correction finie."""
    n = 0
    for copie in (Copie.objects.filter(resultat_notifie=False, planification__date_limite__lte=timezone.now())
                  .select_related("planification__exercice", "inscription__apprenant")):
        n += notifier_resultat(copie)
    return n
