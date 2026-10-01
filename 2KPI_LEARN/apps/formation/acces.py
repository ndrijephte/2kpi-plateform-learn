"""Autorisation d'accès des apprenants aux contenus (modules, séances, ressources, quiz).

Un apprenant n'accède à un module que si :
1. il a une inscription « en cours » à la formation, rattachée à une promotion ;
2. le module est ouvert pour sa promotion :
   - ouvert / fermé explicitement par le formateur ou l'admin (AccesModule), sinon
   - ouverture automatique (si activée sur la promotion) le lundi de la semaine
     de la première séance du module dans l'agenda de la promotion.
Formateurs et administrateurs ont toujours accès (consultation).
"""
import datetime as dt
from dataclasses import dataclass
from django.db.models import Min
from django.utils import timezone
from apps.core.permissions import APPRENANT, role_de


@dataclass
class EtatAcces:
    ouvert: bool
    motif: str = ""            # explication affichée quand c'est fermé
    date: dt.date | None = None  # date d'ouverture automatique prévue / effective
    source: str = "auto"       # auto | ouvert | ferme | inscription


def etats_modules(inscription, modules):
    """{module_id: EtatAcces} pour une inscription (calcul groupé)."""
    from apps.evaluation.models import Inscription

    modules = list(modules)
    if not inscription or inscription.statut != Inscription.Statut.EN_COURS:
        return {m.id: EtatAcces(False, "Ton inscription à cette formation n'est pas active.",
                                source="inscription") for m in modules}
    if not inscription.promotion_id:
        return {m.id: EtatAcces(False, "Tu n'es rattaché à aucune promotion.", source="inscription")
                for m in modules}
    return etats_promotion(inscription.promotion, modules)


def etats_promotion(promo, modules):
    """{module_id: EtatAcces} des modules pour une promotion (2 requêtes)."""
    from apps.agenda.models import AccesModule, Evenement

    modules = list(modules)
    decisions = dict(AccesModule.objects.filter(promotion=promo).values_list("module_id", "etat"))
    premieres = dict(Evenement.objects.filter(promotion=promo, seance__module__in=modules)
                     .values("seance__module").annotate(d=Min("date_debut"))
                     .values_list("seance__module", "d"))
    aujourd_hui = timezone.localdate()
    etats = {}
    for m in modules:
        decision = decisions.get(m.id, AccesModule.Etat.AUTO)
        if decision == AccesModule.Etat.OUVERT:
            etats[m.id] = EtatAcces(True, source="ouvert")
        elif decision == AccesModule.Etat.FERME:
            etats[m.id] = EtatAcces(False, "Ce module a été fermé par ton formateur.", source="ferme")
        elif promo.ouverture_auto and premieres.get(m.id):
            jour = timezone.localtime(premieres[m.id]).date()
            ouverture = jour - dt.timedelta(days=jour.weekday())
            etats[m.id] = EtatAcces(aujourd_hui >= ouverture,
                                    f"Ce module s'ouvrira le {ouverture:%d/%m/%Y}.", ouverture)
        else:
            etats[m.id] = EtatAcces(False, "Ce module n'est pas encore ouvert par ton formateur.")
    return etats


def acces_module(user, module):
    """EtatAcces d'un utilisateur pour un module."""
    if role_de(user) != APPRENANT:
        return EtatAcces(True, source="staff")
    from apps.evaluation.models import Inscription
    insc = (Inscription.objects.filter(apprenant=user, formation_id=module.formation_id)
            .select_related("promotion").order_by("-id").first())
    return etats_modules(insc, [module])[module.id]
