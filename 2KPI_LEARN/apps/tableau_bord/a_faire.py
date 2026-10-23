"""Liste « À faire » de chaque rôle, en tête du tableau de bord : ce que le workflow attend de
la personne, du plus urgent au moins urgent, chaque ligne menant à l'écran où agir."""
import datetime as dt
from dataclasses import dataclass
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from apps.agenda.models import Evenement, Promotion
from apps.agenda.services import seances_a_pointer
from apps.core.permissions import pilote_promotion, promotions_visibles, q_interventions
from apps.evaluation.models import AutoEvaluation, Inscription, Livrable


@dataclass
class Tache:
    icone: str
    titre: str
    detail: str
    url: str
    urgent: bool = False


def _p(n, mot, pluriel=None):
    return f"{n} {mot if n == 1 else (pluriel or mot + 's')}"


def _trier(taches):
    return sorted(taches, key=lambda t: not t.urgent)  # tri stable : l'ordre de construction reste


# ---------- Administration ----------

def taches_admin(user):
    from apps.agenda import workflow
    from apps.comptes.models import Candidature, Profil
    taches = []
    maintenant = timezone.now()
    actives = list(Promotion.objects.filter(active=True).select_related("formation", "formateur"))

    n = Candidature.objects.filter(statut=Candidature.Statut.NOUVELLE).count()
    if n:
        taches.append(Tache("inbox", f"{_p(n, 'candidature')} à traiter", "Reçues du site vitrine ou à la création de compte",
                            reverse("comptes:candidatures")))

    for promo in actives:
        pilotage = reverse("agenda:pilotage", args=[promo.pk])
        admises = promo.inscriptions.filter(statut=Inscription.Statut.ADMISE)
        if admises.exists() and promo.statut in Promotion.STATUTS_ADMISSION:
            payees = admises.exclude(paiement=Inscription.Paiement.EN_ATTENTE).count()
            taches.append(Tache("user-check", f"{_p(admises.count(), 'inscription')} à confirmer — {promo.nom}",
                                f"{payees} avec paiement renseigné" if payees else "Paiement à renseigner avant confirmation",
                                pilotage, urgent=promo.statut == Promotion.Statut.EN_COURS or promo.date_debut
                                <= timezone.localdate() + dt.timedelta(days=7)))
        if promo.statut in (Promotion.Statut.PLANIFIEE, Promotion.Statut.INSCRIPTIONS, Promotion.Statut.PRETE):
            jours = (promo.date_debut - timezone.localdate()).days
            if promo.statut != Promotion.Statut.PRETE and jours <= 14:
                quand = "aujourd'hui" if jours == 0 else (f"dans {_p(jours, 'jour')}" if jours > 0 else f"depuis le {promo.date_debut:%d/%m}")
                taches.append(Tache("alert", f"{promo.nom} : démarrage {quand}",
                                    f"Encore « {promo.get_statut_display()} » — voir ce qui manque", pilotage, urgent=True))
        if promo.statut == Promotion.Statut.EN_COURS and all(
                c.ok for c in workflow.conditions_promotion(promo, Promotion.Statut.CLOTUREE)):
            taches.append(Tache("award", f"{promo.nom} : prête à être clôturée",
                                "Séances, présences et évaluations complètes : calculer les résultats", pilotage))
        if promo.formateur_id is None and not promo.affectations.exists() and promo.statut != Promotion.Statut.CLOTUREE:
            taches.append(Tache("briefcase", f"{promo.nom} : aucun formateur", "Désigner le référent ou affecter des formateurs",
                                reverse("agenda:affectations", args=[promo.pk]), urgent=promo.statut == Promotion.Statut.EN_COURS))

    oublis = seances_a_pointer(Evenement.objects.all(), maintenant - dt.timedelta(days=3)).select_related("promotion")
    par_promo = {}
    for ev in oublis:
        par_promo.setdefault(ev.promotion, []).append(ev)
    for promo, evs in par_promo.items():
        taches.append(Tache("clock", f"{promo.nom} : {_p(len(evs), 'feuille')} de présence en retard",
                            "Séances de plus de 3 jours sans présences — relancer le formateur",
                            reverse("agenda:planning", args=[promo.pk]), urgent=True))

    n = (get_user_model().objects.filter(profil__role=Profil.Role.APPRENANT, is_active=True)
         .exclude(inscriptions__promotion__isnull=False).count())
    if n:
        taches.append(Tache("graduation-cap", f"{_p(n, 'apprenant')} sans promotion", "Ils ne voient ni agenda ni progression",
                            reverse("comptes:utilisateurs") + "?role=apprenant"))
    return _trier(taches)


# ---------- Formateur ----------

def taches_formateur(user):
    taches = []
    promos = promotions_visibles(user).filter(active=True)
    a_pointer = list(seances_a_pointer(Evenement.objects.filter(q_interventions(user), promotion__in=promos))
                     .select_related("promotion").order_by("date_debut"))
    if a_pointer:
        premiere = a_pointer[0]
        taches.append(Tache("user-check", f"{_p(len(a_pointer), 'feuille')} de présence à enregistrer",
                            f"La plus ancienne : {premiere.libelle} ({timezone.localtime(premiere.date_debut):%d/%m})",
                            reverse("agenda:presences", args=[premiere.pk]),
                            urgent=premiere.date_debut < timezone.now() - dt.timedelta(days=1)))
    n = Livrable.objects.filter(q_interventions(user, promotion="inscription__promotion"), rendu=True,
                                note_sur_20__isnull=True, inscription__promotion__in=promos).count()
    if n:
        taches.append(Tache("clipboard-check", f"{_p(n, 'livrable')} à corriger", "Rendus par les apprenants",
                            reverse("evaluation:livrables")))
    n = AutoEvaluation.objects.filter(q_interventions(user, promotion="inscription__promotion", module="objectif__seance__module"),
                                      besoin_aide=True, inscription__promotion__in=promos).count()
    if n:
        taches.append(Tache("target", f"{_p(n, 'demande')} d'aide", "Signalées dans les auto-évaluations",
                            reverse("tableau_bord:accueil") + "#aides"))
    # Référent : évaluation finale à compléter une fois toutes les séances passées
    from apps.evaluation.grille import evaluation_incomplete
    for promo in promos.filter(statut=Promotion.Statut.EN_COURS).select_related("formation"):
        if not pilote_promotion(user, promo):
            continue
        reste = promo.evenements.filter(Q(date_debut__gt=timezone.now()), ~Q(statut=Evenement.Statut.ANNULE)).exists()
        if reste:
            continue
        criteres = list(promo.formation.criteres.all())
        incompletes = [i for i in promo.inscriptions.filter(statut=Inscription.Statut.EN_COURS).select_related("formation")
                       if evaluation_incomplete(i, criteres)]
        if incompletes:
            taches.append(Tache("award", f"{promo.nom} : évaluation finale à compléter",
                                f"{_p(len(incompletes), 'apprenant')} sans note de projet ou de soutenance",
                                reverse("evaluation:evaluation_promotion", args=[promo.pk]), urgent=True))
    return _trier(taches)


# ---------- Apprenant ----------

def taches_apprenant(user, inscription):
    from apps.evaluation import attestation, grille
    taches = []
    if inscription is None:
        return taches
    if attestation.est_valide(inscription):
        taches.append(Tache("award", "Ton attestation de réussite est disponible",
                            f"{inscription.formation.titre} — n° {inscription.code_attestation}",
                            reverse("evaluation:attestation_pdf", args=[inscription.pk])))
    if inscription.statut == Inscription.Statut.ADMISE:
        taches.append(Tache("clock", "Inscription en attente de confirmation",
                            "Ton espace s'ouvre dès que l'administration confirme ton inscription (paiement).",
                            reverse("comptes:profil")))
    if inscription.statut in (Inscription.Statut.ADMISE, Inscription.Statut.CONFIRMEE, Inscription.Statut.EN_COURS):
        etats = grille.etats_prerequis(inscription)
        restants = [p for p, statut in etats if statut != grille.OK]
        if restants:
            obligatoires = [p for p in restants if p.obligatoire]
            taches.append(Tache("list-checks", f"{_p(len(restants), 'prérequis', 'prérequis')} à finaliser",
                                ", ".join(p.libelle for p in restants[:3]) + ("…" if len(restants) > 3 else ""),
                                reverse("comptes:profil_modifier"), urgent=bool(obligatoires)))
    return _trier(taches)
