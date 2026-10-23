"""Autorisation d'accès aux contenus (modules, séances, ressources, quiz) - décidée par l'admin.

Un apprenant n'accède à un module que si :
1. il a une inscription confirmée (ou en cours) à la formation, rattachée à une promotion - agenda/workflow.py ;
2. le module est ouvert pour sa promotion, par décision de l'admin :
   - ouvert / fermé explicitement (AccesModule), sinon
   - ouverture automatique (si l'admin l'a activée sur la promotion) le lundi de la semaine
     de la première séance du module dans l'agenda de la promotion.
Un formateur n'accède qu'aux modules que l'admin lui a attribués (référent d'une promotion :
tous ses modules ; sinon les modules cochés de son affectation). L'admin a toujours accès.
"""
import datetime as dt
from dataclasses import dataclass
from django.db.models import Min
from django.utils import timezone
from apps.core.permissions import ADMIN, APPRENANT, modules_gerables, role_de


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
    if not inscription or not inscription.est_active:
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
            etats[m.id] = EtatAcces(False, "Ce module est fermé pour le moment.", source="ferme")
        elif promo.ouverture_auto and premieres.get(m.id):
            jour = timezone.localtime(premieres[m.id]).date()
            ouverture = jour - dt.timedelta(days=jour.weekday())
            etats[m.id] = EtatAcces(aujourd_hui >= ouverture,
                                    f"Ce module s'ouvrira le {ouverture:%d/%m/%Y}.", ouverture)
        else:
            etats[m.id] = EtatAcces(False, "Ce module n'est pas encore ouvert.")
    return etats


NON_ATTRIBUE = "Ce module ne t'a pas été attribué par l'administration."


def etats_formateur(user, modules):
    """{module_id: EtatAcces} pour un formateur ou un admin (modules attribués uniquement)."""
    modules = list(modules)
    if role_de(user) == ADMIN:
        return {m.id: EtatAcces(True, source="staff") for m in modules}
    autorises = set(modules_gerables(user).filter(pk__in=[m.id for m in modules]).values_list("pk", flat=True))
    return {m.id: EtatAcces(True, source="affectation") if m.id in autorises
            else EtatAcces(False, NON_ATTRIBUE, source="affectation") for m in modules}


def acces_module(user, module):
    """EtatAcces d'un utilisateur pour un module."""
    if role_de(user) != APPRENANT:
        return etats_formateur(user, [module])[module.id]
    from apps.evaluation.models import Inscription
    insc = (Inscription.objects.filter(apprenant=user, formation_id=module.formation_id)
            .select_related("promotion").order_by("-id"))
    insc = next((i for i in insc if i.est_active and i.promotion_id), None) or insc.first()
    return etats_modules(insc, [module])[module.id]


def diagnostic_apprenant(user):
    """Pourquoi un apprenant accède (ou non) aux cours : étapes vérifiées dans l'ordre, pour l'admin.
    Retourne {"ok": bool, "etapes": [(ok, libellé, détail)], "ouverts": [codes], "inscription": insc}."""
    from apps.agenda.models import AccesModule
    from apps.evaluation.models import Inscription
    from apps.evaluation.utils import inscription_courante
    etapes = []

    def etape(ok, libelle, detail=""):
        etapes.append((ok, libelle, detail))
        return ok

    resultat = {"ok": False, "etapes": etapes, "ouverts": [], "inscription": None}
    role = role_de(user)
    if not etape(role == APPRENANT, "Rôle apprenant",
                 "" if role == APPRENANT else f"Le compte a le rôle « {role} » : il ne suit pas les cours comme apprenant."):
        return resultat
    if not etape(user.is_active, "Compte actif", "" if user.is_active else "Le compte est désactivé."):
        return resultat
    insc = inscription_courante(user)
    resultat["inscription"] = insc
    if not etape(insc is not None, "Inscription à une formation",
                 "Aucune inscription : rattache-le à une promotion (Utilisateurs › Promotion)." if insc is None
                 else f"{insc.formation}"):
        return resultat
    autres = Inscription.objects.filter(apprenant=user).exclude(pk=insc.pk).count()
    if autres:
        etapes[-1] = (True, "Inscription à une formation",
                      f"{insc.formation} (prise en compte ; {autres} autre{'s' if autres > 1 else ''} inscription{'s' if autres > 1 else ''} ignorée{'s' if autres > 1 else ''})")
    if not etape(insc.est_active, "Inscription confirmée",
                 "" if insc.est_active else f"Statut actuel : « {insc.get_statut_display()} »."
                 + (" Confirme-la (paiement reçu ou exonération) dans Promotions › Pilotage."
                    if insc.statut == Inscription.Statut.ADMISE else "")):
        return resultat
    promo = insc.promotion
    if not etape(promo is not None, "Rattachement à une promotion",
                 "Aucune promotion : choisis-la sur la fiche du compte." if promo is None else promo.nom):
        return resultat
    if promo.formation_id != insc.formation_id:
        etape(False, "Promotion de la même formation",
              f"La promotion « {promo.nom} » relève de « {promo.formation} », l'inscription de « {insc.formation} ». "
              "Rattache-le de nouveau à la promotion.")
        return resultat
    modules = list(insc.formation.modules.order_by("ordre"))
    etats = etats_promotion(promo, modules)
    resultat["ouverts"] = [m.code for m in modules if etats[m.id].ouvert]
    if resultat["ouverts"]:
        etape(True, "Modules ouverts pour sa promotion", ", ".join(resultat["ouverts"]))
        resultat["ok"] = True
    else:
        ailleurs = sorted({f"{a.module.code} ({a.promotion.nom})" for a in AccesModule.objects.filter(
            module__formation_id=insc.formation_id, etat=AccesModule.Etat.OUVERT).exclude(promotion=promo)
            .select_related("module", "promotion")})
        etape(False, "Modules ouverts pour sa promotion",
              f"Aucun module ouvert pour « {promo.nom} » (Promotions › Accès)."
              + (f" Ouverts dans d'autres promotions seulement : {', '.join(ailleurs)}." if ailleurs else "")
              + ("" if modules else " La formation n'a encore aucun module."))
    return resultat
