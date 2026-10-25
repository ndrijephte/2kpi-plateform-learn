"""Workflow 2KPI : cycle de vie des promotions et des inscriptions, identique pour toute formation.

Promotion   : planifiée → inscriptions ouvertes → prête → en cours → clôturée → archivée
Inscription : admise → confirmée → en cours → validée / non validée   (abandon possible avant la clôture)

Aucun statut ne se modifie à la main : tout passe par changer_statut_promotion() et
changer_statut_inscription(), qui vérifient les conditions de passage (check-list affichée à
l'administration), appliquent les effets (vitrine, notifications, résultats) et journalisent le
changement (JournalStatut). Le démarrage à la date prévue est fait par la commande quotidienne
`workflow_quotidien`.
"""
import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from .models import Evenement, Notification, Promotion

P = Promotion.Statut


class TransitionRefusee(Exception):
    """Passage impossible : `manques` liste les conditions non remplies (libellés lisibles)."""
    def __init__(self, manques):
        self.manques = manques
        super().__init__(" ; ".join(manques))


@dataclass
class Condition:
    ok: bool
    libelle: str
    detail: str = ""
    cle: str = ""  # repère pour l'interface (ex. mise à jour en direct dans la page de publication)


# (de, vers) → libellé du bouton
TRANSITIONS_PROMOTION = {
    (P.PLANIFIEE, P.INSCRIPTIONS): "Publier sur le site (ouvrir les inscriptions)",
    (P.INSCRIPTIONS, P.PLANIFIEE): "Retirer du site (repasser en brouillon)",
    (P.INSCRIPTIONS, P.PRETE): "Déclarer prête à démarrer",
    (P.PRETE, P.INSCRIPTIONS): "Revenir aux inscriptions",
    (P.PRETE, P.EN_COURS): "Démarrer la session",
    (P.EN_COURS, P.CLOTUREE): "Clôturer et calculer les résultats",
    (P.CLOTUREE, P.ARCHIVEE): "Archiver",
    (P.PLANIFIEE, P.ARCHIVEE): "Annuler la session",
    (P.INSCRIPTIONS, P.ARCHIVEE): "Annuler la session",
    (P.PRETE, P.ARCHIVEE): "Annuler la session",
}
ETAPES_PROMOTION = [P.PLANIFIEE, P.INSCRIPTIONS, P.PRETE, P.EN_COURS, P.CLOTUREE, P.ARCHIVEE]


def _inscription_model():
    from apps.evaluation.models import Inscription
    return Inscription


def _journaliser(par, motif, de, vers, promotion=None, inscription=None):
    from apps.evaluation.models import JournalStatut
    JournalStatut.objects.create(promotion=promotion or (inscription.promotion if inscription else None),
                                 inscription=inscription, de=de, vers=vers, motif=motif[:300], par=par)


def _pluriel(n, mot):
    return f"{n} {mot}{'s' if n > 1 else ''}"


# ---------- Conditions de passage d'une promotion ----------

def _conditions_preparation(promo):
    formation = promo.formation
    modules = list(formation.modules.annotate(nb=Count("seances")).order_by("ordre"))
    vides = [m.code for m in modules if not m.nb]
    return [
        Condition(formation.active, "Formation active", "" if formation.active else "Paramètres › Formations."),
        Condition(bool(modules) and not vides, "Chaque module a au moins une séance",
                  "La formation n'a aucun module." if not modules else
                  (f"Sans séance : {', '.join(vides)}." if vides else _pluriel(len(modules), "module"))),
        Condition(promo.formateur_id is not None, "Formateur référent désigné",
                  str(promo.formateur.get_full_name() or promo.formateur) if promo.formateur_id
                  else "À choisir dans la fiche de la session.", cle="formateur"),
        Condition(promo.evenements.exists(), "Calendrier généré",
                  _pluriel(promo.evenements.count(), "séance datée") if promo.evenements.exists()
                  else "À générer depuis la fiche de la session.", cle="calendrier"),
        Condition(promo.places_total > 0, "Nombre de places renseigné",
                  "" if promo.places_total > 0 else "À renseigner dans la fiche de la session.", cle="places"),
    ]


def _nb_confirmees(promo):
    return promo.inscriptions.filter(statut__in=_inscription_model().STATUTS_ACTIFS).count()


def _condition_effectif(promo):
    n = _nb_confirmees(promo)
    return Condition(n >= promo.effectif_minimum,
                     f"Au moins {_pluriel(promo.effectif_minimum, 'inscription confirmée')}",
                     f"{_pluriel(n, 'confirmée')} actuellement.")


def _conditions_cloture(promo):
    Inscription = _inscription_model()
    a_venir = promo.evenements.filter(statut__in=[Evenement.Statut.PLANIFIE, Evenement.Statut.CONFIRME,
                                                  Evenement.Statut.REPORTE])
    nb_actifs = promo.inscriptions.filter(statut=Inscription.Statut.EN_COURS).count()
    realises = list(promo.evenements.filter(statut=Evenement.Statut.REALISE).annotate(
        nb=Count("presences", filter=Q(presences__inscription__statut=Inscription.Statut.EN_COURS))))
    sans_presences = [e for e in realises if e.nb < nb_actifs]
    from apps.evaluation.models import Livrable
    a_corriger = Livrable.objects.filter(inscription__promotion=promo, inscription__statut=Inscription.Statut.EN_COURS,
                                         rendu=True, note_sur_20__isnull=True).count()
    from apps.evaluation.grille import evaluation_incomplete
    criteres = list(promo.formation.criteres.all())
    incompletes = [i for i in promo.inscriptions.filter(statut=Inscription.Statut.EN_COURS)
                   .select_related("apprenant", "formation", "soutenance")
                   if evaluation_incomplete(i, criteres)]
    return [
        Condition(not incompletes, "Évaluation finale complète (grille du projet, soutenance)",
                  f"À compléter pour {_pluriel(len(incompletes), 'apprenant')} : "
                  + ", ".join(i.apprenant.get_full_name() or i.apprenant.username for i in incompletes[:5])
                  + ("…" if len(incompletes) > 5 else "") + " (Promotions › Évaluation)." if incompletes else ""),
        Condition(not a_venir.exists(), "Toutes les séances sont réalisées ou annulées",
                  f"{_pluriel(a_venir.count(), 'séance')} encore planifiée(s), confirmée(s) ou reportée(s) (Planning)."
                  if a_venir.exists() else ""),
        Condition(bool(realises), "Au moins une séance réalisée", "" if realises else "Aucune séance réalisée."),
        Condition(not sans_presences, "Présences saisies pour chaque séance réalisée",
                  "Feuilles incomplètes : " + ", ".join(timezone.localtime(e.date_debut).strftime("%d/%m")
                                                        for e in sans_presences[:8])
                  + ("…" if len(sans_presences) > 8 else "") if sans_presences else ""),
        Condition(not a_corriger, "Tous les livrables rendus sont notés",
                  f"{_pluriel(a_corriger, 'livrable')} à corriger." if a_corriger else ""),
    ]


def conditions_promotion(promo, cible):
    """Check-list (liste de Condition) du passage de la promotion vers `cible`."""
    if (promo.statut, cible) not in TRANSITIONS_PROMOTION:
        return [Condition(False, "Passage autorisé",
                          f"Impossible de passer de « {promo.get_statut_display()} » à « {P(cible).label} ».")]
    if cible == P.INSCRIPTIONS and promo.statut == P.PLANIFIEE:
        return _conditions_preparation(promo)
    if cible == P.PRETE:
        return _conditions_preparation(promo) + [_condition_effectif(promo)]
    if cible == P.EN_COURS:
        debut = promo.date_debut <= timezone.localdate()
        return [Condition(debut, "Date de début atteinte",
                          "" if debut else f"Démarrage prévu le {promo.date_debut:%d/%m/%Y} (automatique ce jour-là)."),
                _condition_effectif(promo)]
    if cible == P.CLOTUREE:
        return _conditions_cloture(promo)
    if cible == P.ARCHIVEE and promo.statut != P.CLOTUREE:
        n = _nb_confirmees(promo)
        return [Condition(not n, "Aucune inscription confirmée",
                          f"{_pluriel(n, 'inscription confirmée')} : passe-les d'abord en abandon "
                          "(remboursement, report sur une autre session)." if n else "")]
    return []


def actions_promotion(promo):
    """Passages possibles depuis le statut actuel : [{cible, libelle, conditions, possible}]."""
    actions = []
    for (de, vers), libelle in TRANSITIONS_PROMOTION.items():
        if de == promo.statut:
            conditions = conditions_promotion(promo, vers)
            actions.append({"cible": vers, "libelle": libelle, "conditions": conditions,
                            "possible": all(c.ok for c in conditions)})
    return actions


# ---------- Changement de statut d'une promotion ----------

@transaction.atomic
def changer_statut_promotion(promo, cible, par=None, motif=""):
    """Applique le passage (ou lève TransitionRefusee). Retourne un message de synthèse."""
    manques = [f"{c.libelle} - {c.detail}" if c.detail else c.libelle
               for c in conditions_promotion(promo, cible) if not c.ok]
    if manques:
        raise TransitionRefusee(manques)
    de = promo.statut
    promo.statut = cible
    champs = ["statut"]
    # Le site vitrine annonce exactement les sessions ouvertes aux inscriptions (ou prêtes) : l'ouverture
    # par l'administration vaut publication, la fermeture ou le démarrage la retirent.
    publiee = cible in Promotion.STATUTS_PUBLIABLES
    if promo.publiee_vitrine != publiee:
        promo.publiee_vitrine = publiee
        champs.append("publiee_vitrine")
    promo.save(update_fields=champs)
    _journaliser(par, motif, de, cible, promotion=promo)
    message = f"« {promo.nom} » : {promo.get_statut_display()}."
    if "publiee_vitrine" in champs:
        message += " Annoncée sur le site vitrine." if publiee else " Retirée du site vitrine."
    if cible == P.INSCRIPTIONS:
        from apps.comptes.services import prevenir_interesses
        n = prevenir_interesses(promo)
        message += f" {_pluriel(n, 'personne intéressée')} prévenue(s) par e-mail." if n else ""
    if cible == P.EN_COURS:
        message += _demarrer(promo, par)
    elif cible == P.CLOTUREE:
        message += _cloturer(promo, par)
    elif cible == P.ARCHIVEE and de != P.CLOTUREE:
        n = _abandonner_restantes(promo, par, "Session annulée")
        message += f" {_pluriel(n, 'inscription admise')} passée(s) en abandon." if n else ""
    return message


def desarchiver(promo, par, motif=""):
    """Rend une promotion archivée à son statut précédent (erreur de manipulation)."""
    if promo.statut != P.ARCHIVEE:
        raise TransitionRefusee(["La promotion n'est pas archivée."])
    precedent = promo.journal.filter(inscription__isnull=True, vers=P.ARCHIVEE).exclude(de="").first()
    cible = precedent.de if precedent else P.CLOTUREE
    promo.statut = cible
    promo.save(update_fields=["statut"])
    _journaliser(par, motif or "Désarchivage", P.ARCHIVEE, cible, promotion=promo)
    return f"« {promo.nom} » : de nouveau « {promo.get_statut_display()} »."


def _destinataires(promo):
    """Apprenants actifs + formateurs (référent et affectés) de la promotion."""
    Inscription = _inscription_model()
    apprenants = [i.apprenant for i in promo.inscriptions.filter(statut__in=Inscription.STATUTS_ACTIFS)
                  .select_related("apprenant")]
    formateurs = {a.formateur for a in promo.affectations.select_related("formateur")}
    if promo.formateur:
        formateurs.add(promo.formateur)
    return apprenants, list(formateurs)


def _demarrer(promo, par):
    from .services import notifier
    Inscription = _inscription_model()
    for insc in promo.inscriptions.filter(statut=Inscription.Statut.CONFIRMEE):
        changer_statut_inscription(insc, Inscription.Statut.EN_COURS, par=par, motif="Démarrage de la promotion",
                                   systeme=True)
    apprenants, formateurs = _destinataires(promo)
    notifier(apprenants + formateurs, titre=f"La session « {promo.nom} » démarre",
             message="Retrouve le calendrier dans ton agenda ; les modules s'ouvrent au fil des semaines.",
             type=Notification.Type.INFO, expediteur=par, lien=reverse("agenda:mon_agenda"))
    restantes = promo.inscriptions.filter(statut=Inscription.Statut.ADMISE).count()
    return (f" {_pluriel(len(apprenants), 'apprenant')} en formation."
            + (f" {_pluriel(restantes, 'inscription')} encore à confirmer." if restantes else ""))


def resultat_inscription(insc, nb_realises):
    """(taux d'assiduité en %, note finale /20, validée ?) selon les règles de la formation."""
    from apps.evaluation.models import Presence
    from apps.tableau_bord.services import synthese
    presents = insc.presences.filter(evenement__promotion_id=insc.promotion_id,
                                     evenement__statut=Evenement.Statut.REALISE,
                                     statut__in=[Presence.Statut.PRESENT, Presence.Statut.RETARD]).count()
    taux = round(100 * presents / nb_realises) if nb_realises else 0
    note = Decimal(str(synthese(insc)["note_globale"])).quantize(Decimal("0.01"))
    f = insc.formation
    return taux, note, taux >= f.seuil_assiduite and note >= f.note_minimale


def _cloturer(promo, par):
    from .services import notifier
    Inscription = _inscription_model()
    f = promo.formation
    nb_realises = promo.evenements.filter(statut=Evenement.Statut.REALISE).count()
    validees = 0
    inscriptions = list(promo.inscriptions.filter(statut=Inscription.Statut.EN_COURS).select_related("apprenant", "formation"))
    from django.db.models import Sum
    for insc in inscriptions:
        insc.taux_assiduite, insc.note_finale, ok = resultat_inscription(insc, nb_realises)
        insc.heures_suivies = insc.presences.filter(evenement__promotion=promo, evenement__statut=Evenement.Statut.REALISE
                                                    ).aggregate(h=Sum("duree_realisee_h"))["h"] or 0
        insc.save(update_fields=["taux_assiduite", "note_finale", "heures_suivies"])
        cible = Inscription.Statut.VALIDEE if ok else Inscription.Statut.NON_VALIDEE
        changer_statut_inscription(insc, cible, par=par, systeme=True,
                                   motif=f"Clôture : assiduité {insc.taux_assiduite} % (min. {f.seuil_assiduite} %), "
                                         f"note {insc.note_finale}/20 (min. {f.note_minimale}/20)")
        validees += ok
        notifier([insc.apprenant], titre=f"Résultat de la formation « {promo.nom} »",
                 message=f"{insc.get_statut_display()} - assiduité {insc.taux_assiduite} %, "
                         f"note finale {insc.note_finale}/20."
                         + (" Ton attestation de réussite est disponible sur ton tableau de bord." if ok else ""),
                 type=Notification.Type.INFO, expediteur=par, lien=reverse("tableau_bord:accueil"))
    abandons = _abandonner_restantes(promo, par, "Inscription non confirmée à la clôture de la session")
    return (f" {validees}/{len(inscriptions)} validée(s)."
            + (f" {_pluriel(abandons, 'inscription')} non confirmée(s) passée(s) en abandon." if abandons else ""))


def _abandonner_restantes(promo, par, motif):
    Inscription = _inscription_model()
    restantes = list(promo.inscriptions.filter(statut__in=[Inscription.Statut.ADMISE, Inscription.Statut.CONFIRMEE]))
    for insc in restantes:
        changer_statut_inscription(insc, Inscription.Statut.ABANDON, par=par, motif=motif, systeme=True)
    return len(restantes)


# ---------- Inscriptions ----------

def _transitions_inscription():
    S = _inscription_model().Statut
    # Les passages « en cours » (démarrage) et « validée / non validée » (clôture) sont réservés au système.
    return {
        (S.ADMISE, S.CONFIRMEE): "Confirmer",
        (S.CONFIRMEE, S.ADMISE): "Annuler la confirmation",
        (S.ADMISE, S.ABANDON): "Abandon",
        (S.CONFIRMEE, S.ABANDON): "Abandon",
        (S.EN_COURS, S.ABANDON): "Abandon",
        (S.ABANDON, S.ADMISE): "Réintégrer",
        (S.VALIDEE, S.NON_VALIDEE): "Dérogation : non validée",
        (S.NON_VALIDEE, S.VALIDEE): "Dérogation : validée",
    }


def conditions_inscription(insc, cible, motif=""):
    S = _inscription_model().Statut
    promo = insc.promotion
    conditions = []
    if cible in (S.CONFIRMEE, S.ADMISE) and insc.statut != S.CONFIRMEE:
        ouverte = promo is not None and promo.statut in Promotion.STATUTS_ADMISSION
        conditions.append(Condition(ouverte, "Promotion qui accepte des inscriptions",
                                    "Aucune promotion rattachée." if promo is None else
                                    f"« {promo.nom} » est « {promo.get_statut_display()} »."))
    if cible == S.CONFIRMEE:
        from apps.evaluation.grille import obligatoires_manquants
        conditions.append(Condition(insc.paiement != insc.Paiement.EN_ATTENTE, "Paiement reçu ou exonération",
                                    "Indique le paiement avant de confirmer."))
        manquants = obligatoires_manquants(insc)
        conditions.append(Condition(not manquants, "Prérequis obligatoires remplis",
                                    f"Pas encore « OK » : {', '.join(manquants)}." if manquants else ""))
    if cible in (S.ABANDON, S.VALIDEE, S.NON_VALIDEE):
        conditions.append(Condition(bool(motif.strip()), "Motif renseigné", "Le motif est obligatoire."))
    return conditions


@transaction.atomic
def changer_statut_inscription(insc, cible, par=None, motif="", systeme=False):
    """Applique le passage (ou lève TransitionRefusee). `systeme` : passage déclenché par la promotion."""
    S = _inscription_model().Statut
    if not systeme:
        if (insc.statut, cible) not in _transitions_inscription():
            raise TransitionRefusee([f"Impossible de passer de « {insc.get_statut_display()} » à « {S(cible).label} »."])
        manques = [f"{c.libelle} - {c.detail}" if c.detail else c.libelle
                   for c in conditions_inscription(insc, cible, motif) if not c.ok]
        if manques:
            raise TransitionRefusee(manques)
    de = insc.statut
    insc.statut = cible
    insc.save(update_fields=["statut"])
    _journaliser(par, motif, de, cible, inscription=insc)
    if cible == S.VALIDEE:  # numéro d'attestation attribué une fois pour toutes
        from apps.evaluation.attestation import delivrer
        delivrer(insc)
    if cible == S.CONFIRMEE and not systeme:
        from .services import notifier
        notifier([insc.apprenant], titre=f"Inscription confirmée : {insc.promotion.nom}",
                 message=f"Démarrage le {insc.promotion.date_debut:%d/%m/%Y}. Tes modules s'ouvriront au fil du calendrier.",
                 type=Notification.Type.INFO, expediteur=par, lien=reverse("formation:modules"))
        if insc.promotion.statut == P.EN_COURS:  # arrivée en cours de session
            changer_statut_inscription(insc, S.EN_COURS, par=par, motif="Promotion déjà démarrée", systeme=True)
    return insc


def actions_inscription(insc):
    return [{"cible": vers, "libelle": libelle} for (de, vers), libelle in _transitions_inscription().items()
            if de == insc.statut]


# ---------- Tâche quotidienne ----------

def demarrages_du_jour(aujourd_hui=None):
    """Démarre les promotions prêtes dont la date est atteinte ; signale aux admins celles qui ne le sont pas.
    Retourne (démarrées, en retard)."""
    from apps.comptes.services import notifier_admins
    aujourd_hui = aujourd_hui or timezone.localdate()
    demarrees, en_retard = [], []
    for promo in Promotion.objects.filter(statut=P.PRETE, date_debut__lte=aujourd_hui):
        try:
            changer_statut_promotion(promo, P.EN_COURS, motif="Démarrage automatique à la date prévue")
            demarrees.append(promo)
        except TransitionRefusee:
            en_retard.append(promo)
    en_retard += list(Promotion.objects.filter(statut__in=[P.PLANIFIEE, P.INSCRIPTIONS], date_debut__lte=aujourd_hui,
                                               date_debut__gte=aujourd_hui - dt.timedelta(days=7)))
    for promo in en_retard:
        titre = f"Démarrage bloqué : {promo.nom}"
        if not Notification.objects.filter(titre=titre).exists():  # une alerte par promotion
            notifier_admins(titre, f"La session devait démarrer le {promo.date_debut:%d/%m/%Y} mais elle est "
                                   f"« {promo.get_statut_display()} ». Ouvre son pilotage pour voir ce qui manque.",
                            lien=reverse("agenda:pilotage", args=[promo.pk]))
    return demarrees, en_retard


def relances_presences(maintenant=None):
    """Feuilles de présence non validées : rappel aux formateurs de la séance le lendemain,
    alerte aux administrateurs après 3 jours. Une seule relance de chaque sorte par séance.
    Retourne (rappels formateurs, alertes admins)."""
    from apps.comptes.services import notifier_admins
    from .services import formateurs_de, notifier, seances_a_pointer
    maintenant = maintenant or timezone.now()
    rappels = alertes = 0
    retard = (seances_a_pointer(Evenement.objects.all(), maintenant - dt.timedelta(days=1))
              .select_related("promotion__formateur", "seance__module"))
    for ev in retard:
        jour = timezone.localtime(ev.date_debut).strftime("%d/%m")
        titre = f"Présences à saisir : {ev.libelle} ({jour})"
        if not Notification.objects.filter(evenement=ev, titre=titre).exists():
            notifier(formateurs_de(ev), titre=titre, type=Notification.Type.RAPPEL, evenement=ev,
                     lien=reverse("agenda:presences", args=[ev.pk]),
                     message=f"« {ev.promotion.nom} » : la feuille de présence de cette séance n'est pas enregistrée. "
                             "Elle conditionne l'assiduité des apprenants et la clôture de la promotion.")
            rappels += 1
        titre_admin = f"Présences non saisies depuis 3 jours : {ev.libelle} ({jour})"
        if ev.date_debut <= maintenant - dt.timedelta(days=3) and not Notification.objects.filter(titre=titre_admin).exists():
            noms = ", ".join(f.get_full_name() or f.username for f in formateurs_de(ev)) or "aucun formateur"
            notifier_admins(titre_admin, f"« {ev.promotion.nom} » · formateur(s) : {noms}.",
                            lien=reverse("agenda:presences", args=[ev.pk]))
            alertes += 1
    return rappels, alertes
