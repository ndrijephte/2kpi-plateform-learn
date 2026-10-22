"""Auto-évaluation des apprenants sur les objectifs de chaque séance.

- L'apprenant se positionne sur chaque objectif (4 niveaux, cf. AutoEvaluation.Niveau), peut
  préciser ce qui le bloque et demander à en reparler avec le formateur ; il se réévalue quand il veut,
  son premier niveau est conservé pour mesurer sa progression.
- Le formateur voit, pour ses séances, la répartition des niveaux par objectif, les commentaires et
  les demandes d'aide (qui lui sont aussi notifiées).
"""
from collections import Counter
from django.db import transaction
from apps.formation.models import ObjectifSeance
from .models import AutoEvaluation

NIVEAUX = AutoEvaluation.Niveau


def echelle():
    """[(valeur, libellé, explication)] des 4 niveaux, pour les formulaires et légendes."""
    return [(v, lib, AutoEvaluation.AIDE[v]) for v, lib in NIVEAUX.choices]


def evaluations_de(inscription, objectifs):
    """{objectif_id: AutoEvaluation} de l'inscription pour ces objectifs."""
    if not inscription:
        return {}
    return {a.objectif_id: a for a in AutoEvaluation.objects.filter(inscription=inscription, objectif__in=objectifs)}


@transaction.atomic
def enregistrer(inscription, objectifs, donnees):
    """Enregistre les réponses du formulaire (niveau_<id>, commentaire_<id>, aide_<id>).
    Un objectif sans niveau choisi est ignoré (réponse partielle possible).
    Retourne (nb_enregistrees, objectifs pour lesquels l'aide vient d'être demandée)."""
    existantes = evaluations_de(inscription, objectifs)
    n, nouvelles_aides = 0, []
    for o in objectifs:
        brut = donnees.get(f"niveau_{o.pk}", "")
        if not brut.isdigit() or int(brut) not in NIVEAUX.values:
            continue
        niveau = int(brut)
        commentaire = (donnees.get(f"commentaire_{o.pk}") or "").strip()[:500]
        aide = bool(donnees.get(f"aide_{o.pk}"))
        a = existantes.get(o.pk)
        if a is None:
            a = AutoEvaluation(inscription=inscription, objectif=o, niveau_initial=niveau)
        elif a.niveau == niveau and a.commentaire == commentaire and a.besoin_aide == aide:
            n += 1
            continue
        if aide and not a.besoin_aide:
            nouvelles_aides.append(o)
        a.niveau, a.commentaire, a.besoin_aide = niveau, commentaire, aide
        a.save()
        n += 1
    return n, nouvelles_aides


def intervenants(promotion, module):
    """Formateurs qui interviennent sur ce module dans cette promotion (référent + affectations)."""
    from django.db.models import Q
    users = [promotion.formateur] if promotion.formateur_id else []
    for a in (promotion.affectations.filter(Q(tous_les_modules=True) | Q(modules=module))
              .select_related("formateur").distinct()):
        if a.formateur not in users and a.formateur.is_active:
            users.append(a.formateur)
    return users


def signaler_besoin_aide(inscription, seance, objectifs):
    """Notifie les formateurs de la séance qu'un apprenant demande de l'aide."""
    from apps.agenda.models import Notification
    from apps.agenda.services import notifier
    if not objectifs or not inscription.promotion_id:
        return
    apprenant = inscription.apprenant.get_full_name() or inscription.apprenant.username
    notifier(intervenants(inscription.promotion, seance.module),
             titre=f"Demande d'aide : {apprenant} ({seance.module.code})",
             message=f"Séance « {seance.theme or seance} » — objectif(s) : "
                     + " ; ".join(o.libelle for o in objectifs),
             type=Notification.Type.INFO, expediteur=inscription.apprenant)


def apprenants_concernes(seance):
    """Apprenants (inscription en cours, promotion active) pour qui le module de la séance est ouvert."""
    from apps.formation.acces import etats_promotion
    from .models import Inscription
    inscriptions = (Inscription.objects.filter(formation_id=seance.module.formation_id, statut=Inscription.Statut.EN_COURS,
                                               promotion__active=True, apprenant__is_active=True)
                    .select_related("apprenant", "promotion"))
    ouvert, users = {}, []
    for i in inscriptions:
        if i.promotion_id not in ouvert:
            ouvert[i.promotion_id] = etats_promotion(i.promotion, [seance.module])[seance.module_id].ouvert
        if ouvert[i.promotion_id]:
            users.append(i.apprenant)
    return users


def annoncer_objectifs(seance, nouveaux, par):
    """Prévient les apprenants concernés que de nouveaux objectifs les attendent (in-app, sans e-mail)."""
    from apps.agenda.models import Notification
    from apps.agenda.services import notifier
    if not nouveaux:
        return 0
    destinataires = apprenants_concernes(seance)
    n = len(nouveaux)
    notifier(destinataires, titre=f"{seance.module.code} : {n} objectif{'s' if n > 1 else ''} à auto-évaluer",
             message=f"Séance « {seance.theme or seance} » — " + " ; ".join(o.libelle for o in nouveaux)
                     + ". Positionne-toi sur la page de la séance.",
             type=Notification.Type.INFO, envoyer_email=False, expediteur=par)
    return len(destinataires)


def bilan_seance(evaluations, objectifs):
    """Résumé d'une séance pour l'apprenant : nb évalués, nb acquis, niveau moyen."""
    evals = [evaluations[o.pk] for o in objectifs if o.pk in evaluations]
    return {"total": len(objectifs), "evalues": len(evals), "acquis": sum(1 for a in evals if a.acquis),
            "complet": bool(objectifs) and len(evals) == len(objectifs)}


def synthese_apprenant(inscription, modules_ouverts=None):
    """Vue d'ensemble pour l'apprenant : séances (des modules ouverts) avec leurs objectifs et ses niveaux."""
    objectifs = (ObjectifSeance.objects.filter(actif=True, seance__module__formation_id=inscription.formation_id)
                 .select_related("seance", "seance__module")
                 .order_by("seance__module__ordre", "seance__ordre", "ordre"))
    if modules_ouverts is not None:
        objectifs = objectifs.filter(seance__module_id__in=modules_ouverts)
    objectifs = list(objectifs)
    evals = evaluations_de(inscription, objectifs)
    seances = {}
    for o in objectifs:
        seances.setdefault(o.seance, []).append({"objectif": o, "eval": evals.get(o.pk)})
    reponses = [evals[o.pk] for o in objectifs if o.pk in evals]
    return {
        "seances": [{"seance": s, "lignes": lignes,
                     "bilan": bilan_seance(evals, [l["objectif"] for l in lignes])} for s, lignes in seances.items()],
        "total": len(objectifs), "evalues": len(reponses),
        "acquis": sum(1 for a in reponses if a.acquis),
        "progres": sum(1 for a in reponses if a.progression > 0),
        "a_retravailler": sorted((a for a in reponses if not a.acquis), key=lambda a: (a.niveau, -a.modifie_le.timestamp())),
        "pct_acquis": round(100 * sum(1 for a in reponses if a.acquis) / len(objectifs)) if objectifs else 0,
    }


def synthese_promotion(promotion, seances):
    """Pour chaque séance : objectifs avec répartition des niveaux de la promotion, taux d'acquisition,
    demandes d'aide et commentaires. `seances` : séances visibles par le formateur."""
    inscriptions = list(promotion.inscriptions.exclude(statut="abandon").select_related("apprenant"))
    objectifs = list(ObjectifSeance.objects.filter(actif=True, seance__in=seances)
                     .select_related("seance", "seance__module")
                     .order_by("seance__module__ordre", "seance__ordre", "ordre"))
    reponses = {}
    for a in (AutoEvaluation.objects.filter(objectif__in=objectifs, inscription__in=inscriptions)
              .select_related("inscription__apprenant").order_by("niveau", "inscription__apprenant__last_name")):
        reponses.setdefault(a.objectif_id, []).append(a)
    resultat = {}
    for o in objectifs:
        rep = reponses.get(o.pk, [])
        compte = Counter(a.niveau for a in rep)
        n = len(rep)
        resultat.setdefault(o.seance, []).append({
            "objectif": o, "reponses": rep, "nb": n,
            "repartition": [{"niveau": v, "libelle": lib, "nb": compte.get(v, 0),
                             "pct": round(100 * compte.get(v, 0) / n) if n else 0} for v, lib in NIVEAUX.choices],
            "pct_acquis": round(100 * sum(1 for a in rep if a.acquis) / n) if n else None,
            "aides": [a for a in rep if a.besoin_aide],
            "commentaires": [a for a in rep if a.commentaire],
        })
    lignes = []
    for s, objs in resultat.items():
        repondants = {a.inscription_id for o in objs for a in o["reponses"]}
        lignes.append({"seance": s, "objectifs": objs, "repondants": len(repondants),
                       "aides": sum(len(o["aides"]) for o in objs),
                       "alerte": any(o["pct_acquis"] is not None and o["pct_acquis"] < 50 for o in objs)})
    return {"seances": lignes, "nb_inscrits": len(inscriptions)}
