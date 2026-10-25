import datetime as dt
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse
from django.utils.text import slugify
from apps.core.permissions import (APPRENANT, FORMATEUR, admin_requis, formateur_requis, est_admin,
                                   pilote_promotion, promotions_visibles, q_interventions, role_de)
from apps.evaluation.models import Presence
from apps.evaluation.utils import inscription_courante
from .forms import AnnonceForm, SessionForm
from .models import AccesModule, Affectation, Annonce, Promotion, Evenement, Notification
from .services import (STATUTS_A_POINTER, apprenants_de, generer_agenda, inscriptions_a_pointer, notifier,
                       presences_manquantes, synchroniser_agenda)


def _grouper_par_semaine(evenements):
    groupes = {}
    for ev in evenements:
        an, sem, _ = ev.date_debut.isocalendar()
        groupes.setdefault((an, sem), []).append(ev)
    return [{"label": f"Semaine {sem}", "annee": an, "evenements": evs}
            for (an, sem), evs in sorted(groupes.items())]


@login_required
def mon_agenda(request):
    """Apprenant : agenda de sa promotion. Formateur/admin : séances des promotions pilotées."""
    if role_de(request.user) == APPRENANT:
        insc = inscription_courante(request.user)
        promo = insc.promotion if insc else None
        qs = promo.evenements.all() if promo else Evenement.objects.none()
    else:
        promo = None
        qs = Evenement.objects.filter(q_interventions(request.user), promotion__active=True)
    evenements = list(qs.select_related("seance", "seance__module", "promotion")
                      .order_by("date_debut"))
    maintenant = timezone.now()
    prochaine = next((e for e in evenements
                      if e.date_debut >= maintenant and e.statut != Evenement.Statut.ANNULE), None)
    return render(request, "agenda/mon_agenda.html", {
        "promotion": promo, "semaines": _grouper_par_semaine(evenements),
        "vue_formateur": role_de(request.user) != APPRENANT,
        "prochaine": prochaine, "maintenant": maintenant,
    })


@login_required
def notifications(request):
    if request.method == "POST":
        request.user.notifications.filter(lu=False).update(lu=True)
        return redirect("agenda:notifications")
    liste = request.user.notifications.select_related("evenement", "expediteur", "module__formation")[:50]
    return render(request, "agenda/notifications.html", {"notifications": liste})


@login_required
def notification_ouvrir(request, pk):
    """Clic sur une notification : la marque comme lue et ouvre la page concernée (module, séance…)."""
    n = get_object_or_404(request.user.notifications.select_related("evenement", "module"), pk=pk)
    if not n.lu:
        n.lu = True
        n.save(update_fields=["lu"])
    return redirect(n.destination or "agenda:notifications")


@formateur_requis
def envoyer(request):
    """Admin et formateurs envoient des notifications ; historique des envois."""
    form = AnnonceForm(request.POST or None, auteur=request.user)
    if request.method == "POST" and form.is_valid():
        annonce = form.save(commit=False)
        annonce.expediteur = request.user
        annonce.nb_destinataires = len(form.liste_destinataires)
        annonce.save()
        notifier(form.liste_destinataires, titre=annonce.titre, message=annonce.message,
                 type=Notification.Type.INFO, envoyer_email=annonce.par_email,
                 expediteur=request.user, annonce=annonce, module=annonce.module)
        messages.success(request, f"Notification envoyée à {annonce.nb_destinataires} personne(s).")
        return redirect("agenda:envoyer")
    historique = Annonce.objects.select_related("expediteur", "promotion")
    if not est_admin(request.user):
        historique = historique.filter(expediteur=request.user)
    return render(request, "agenda/envoyer.html", {"form": form, "historique": historique[:30]})


@formateur_requis
def planning(request, promo_id):
    from apps.evaluation.models import Inscription
    promo = get_object_or_404(promotions_visibles(request.user), pk=promo_id)
    evenements = list(promo.evenements.filter(q_interventions(request.user))  # séances de SES modules
                      .select_related("seance", "seance__module")
                      .annotate(nb_presences=Count("presences", filter=Q(
                          presences__inscription__statut__in=Inscription.STATUTS_ACTIFS)))
                      .order_by("date_debut"))
    maintenant = timezone.now()
    for ev in evenements:  # séance commencée dont la feuille de présence n'est pas validée
        ev.commencee = ev.date_debut <= maintenant
        ev.a_pointer = ev.commencee and ev.statut in STATUTS_A_POINTER
    return render(request, "agenda/planning.html",
                  {"promotion": promo, "evenements": evenements, "pilote": pilote_promotion(request.user, promo),
                   "nb_apprenants": inscriptions_a_pointer(promo).count(),
                   "nb_a_pointer": sum(1 for ev in evenements if ev.a_pointer),
                   "statuts": Evenement.Statut.choices})


@formateur_requis
def evenement_action(request, ev_id):
    ev = get_object_or_404(Evenement.objects.filter(q_interventions(request.user)), pk=ev_id)
    if request.method != "POST":
        return redirect("agenda:planning", promo_id=ev.promotion_id)
    action = request.POST.get("action")

    if action == "realiser":  # une séance n'est réalisée qu'avec sa feuille de présence complète
        if ev.date_debut > timezone.now():
            messages.error(request, "La séance n'a pas encore commencé.")
            return redirect("agenda:planning", promo_id=ev.promotion_id)
        manquantes = presences_manquantes(ev)
        if manquantes:
            messages.error(request, f"Saisis d'abord les présences ({manquantes} apprenant{'s' if manquantes > 1 else ''} "
                                    "sans statut) : la séance passe « réalisée » à l'enregistrement de la feuille.")
            return redirect("agenda:presences", ev_id=ev.pk)

    if action in ("confirmer", "realiser", "annuler"):
        ev.statut = {"confirmer": Evenement.Statut.CONFIRME,
                     "realiser": Evenement.Statut.REALISE,
                     "annuler": Evenement.Statut.ANNULE}[action]
        ev.save()
        messages.success(request, f"Séance marquée « {ev.get_statut_display()} ».")

    elif action == "reporter":
        nouvelle = request.POST.get("nouvelle_date")  # format datetime-local
        if nouvelle:
            try:
                naive = dt.datetime.fromisoformat(nouvelle)
                nd = timezone.make_aware(naive)
            except ValueError:
                messages.error(request, "Date invalide.")
                return redirect("agenda:planning", promo_id=ev.promotion_id)
            ancienne = ev.date_debut
            delta = nd - ancienne
            ev.date_debut = nd
            ev.statut = Evenement.Statut.REPORTE
            ev.note = request.POST.get("motif", "")
            ev.save()
            if request.POST.get("decaler_suite"):  # uniquement les séances que l'utilisateur anime
                suivants = (ev.promotion.evenements.filter(q_interventions(request.user), date_debut__gt=ancienne)
                            .exclude(pk=ev.pk))
                for s in suivants:
                    s.date_debut = s.date_debut + delta
                    s.save()
                messages.success(request, "Séance reportée, et la suite décalée d'autant.")
            else:
                messages.success(request, "Séance reportée.")

    elif action == "notifier":
        heure = timezone.localtime(ev.date_debut).strftime("%d/%m à %H:%M")
        notifier(apprenants_de(ev.promotion),
                 titre=f"Séance planifiée : {ev.libelle}",
                 message=f"Rendez-vous le {heure} - {ev.get_mode_display()}"
                         + (f" · {ev.lieu}" if ev.lieu else ""),
                 evenement=ev, type=Notification.Type.AGENDA, expediteur=request.user)
        messages.success(request, "Apprenant(s) notifié(s) (in-app + e-mail si configuré).")

    return redirect("agenda:planning", promo_id=ev.promotion_id)


@formateur_requis
def promotions(request):
    """Liste des sessions. Admin : toutes, création par l'assistant. Formateur : celles où il intervient."""
    from apps.evaluation.models import Inscription
    if request.method == "POST":
        raise PermissionDenied
    liste = list(promotions_visibles(request.user).select_related("formation", "formateur")
                 .prefetch_related("affectations__formateur")
                 .annotate(nb_evenements=Count("evenements", distinct=True),
                           nb_apprenants=Count("inscriptions", distinct=True,
                                               filter=~Q(inscriptions__statut=Inscription.Statut.ABANDON)),
                           nb_a_confirmer=Count("inscriptions", distinct=True,
                                                filter=Q(inscriptions__statut=Inscription.Statut.ADMISE)))
                 .order_by("-active", "-date_debut"))
    for p in liste:
        p.pilote = pilote_promotion(request.user, p)
    return render(request, "agenda/promotions.html", {"promotions": liste, "peut_gerer": est_admin(request.user)})


def _formations_json():
    """Valeurs habituelles et état de préparation de chaque formation active (assistant de création)."""
    from apps.formation.models import Formation
    donnees = {}
    for f in Formation.objects.filter(active=True).annotate(nb_modules=Count("modules", distinct=True)):
        vides = list(f.modules.annotate(nb=Count("seances")).filter(nb=0).values_list("code", flat=True))
        donnees[f.pk] = {
            **SessionForm.valeurs_formation(f), "titre": f.titre, "resume": f.resume or f.description[:300],
            "pret": bool(f.nb_modules) and not vides,
            "detail": ("La formation n'a aucun module." if not f.nb_modules else
                       f"Modules sans séance : {', '.join(vides)} (Paramètres › Formations)." if vides
                       else f"{f.nb_modules} module(s), calendrier généré à la création."),
        }
    return donnees


def _page_session(request, form, promo=None):
    from . import workflow
    contexte = {"form": form, "promo": promo, "creation": promo is None,
                "etape_calendrier": form.etape("calendrier"), "etape_fiche": form.etape("fiche"),
                "etape_avance": form.etape("avance"), "avance_ouvert": any(f.errors for f in form.etape("avance"))}
    if promo is None:
        contexte.update(publiable=True, formations=_formations_json(), inscrits=0, conditions=[
            workflow.Condition(True, "Formation prête", "", cle="formation"),
            workflow.Condition(False, "Formateur référent désigné", "À choisir à l'étape 1.", cle="formateur"),
            workflow.Condition(True, "Nombre de places renseigné", "", cle="places"),
            workflow.Condition(True, "Calendrier généré", "Automatiquement, à la création.", cle="calendrier")])
    else:
        planifiee = promo.statut == Promotion.Statut.PLANIFIEE
        contexte.update(
            publiable=planifiee, retirable=promo.statut == Promotion.Statut.INSCRIPTIONS,
            inscrits=promo.nb_inscrits_actifs, sans_calendrier=not promo.evenements.exists(),
            formations={promo.formation_id: {"titre": promo.formation.titre,
                                             "resume": promo.formation.resume or promo.formation.description[:300]}},
            conditions=workflow.conditions_promotion(promo, Promotion.Statut.INSCRIPTIONS) if planifiee else [])
    return render(request, "agenda/session.html", contexte)


def _publier(request, promo):
    from . import workflow
    try:
        messages.success(request, workflow.changer_statut_promotion(
            promo, Promotion.Statut.INSCRIPTIONS, request.user, "Publiée sur le site vitrine"))
        return True
    except workflow.TransitionRefusee as refus:
        messages.error(request, "Session enregistrée en brouillon, publication impossible : " + " ; ".join(refus.manques))
        return False


@admin_requis
def session_nouvelle(request):
    """Assistant « Nouvelle session » : formation et calendrier, fiche publique (aperçu en direct), publication."""
    form = SessionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        promo = form.save()
        promo.refresh_from_db()
        n = generer_agenda(promo)  # calendrier daté d'office (recalable ensuite depuis le planning)
        if request.POST.get("action") == "publier" and _publier(request, promo):
            return redirect("agenda:promotions")
        if request.POST.get("action") != "publier":
            messages.success(request, f"Session « {promo.nom} » enregistrée en brouillon"
                             + (f", calendrier de {n} séance(s) généré" if n else "") + ".")
        return redirect("agenda:fiche_vitrine", promo_id=promo.pk)
    return _page_session(request, form)


@admin_requis
def fiche_vitrine(request, promo_id):
    """Fiche d'une session existante : modification, publication sur le site vitrine, retrait."""
    from . import workflow
    promo = get_object_or_404(Promotion.objects.select_related("formation", "formateur"), pk=promo_id)
    action = request.POST.get("action", "enregistrer") if request.method == "POST" else ""
    if action == "calendrier":
        n = generer_agenda(promo)
        messages.success(request, f"Calendrier généré : {n} séance(s) datée(s)." if n else "Le calendrier est déjà généré.")
        return redirect("agenda:fiche_vitrine", promo_id=promo.pk)
    if action == "retirer":
        try:
            messages.success(request, workflow.changer_statut_promotion(
                promo, Promotion.Statut.PLANIFIEE, request.user, "Retirée du site vitrine"))
        except workflow.TransitionRefusee as refus:
            messages.error(request, "Retrait impossible : " + " ; ".join(refus.manques))
        return redirect("agenda:fiche_vitrine", promo_id=promo.pk)
    form = SessionForm(request.POST if action in ("enregistrer", "publier") else None, instance=promo)
    if action in ("enregistrer", "publier") and form.is_valid():
        promo = form.save()
        if "date_debut" in form.changed_data and promo.evenements.exists():
            recales, _ = synchroniser_agenda(promo)  # seules les séances encore « planifiées » bougent
            messages.info(request, f"Nouvelle date de début : {recales} séance(s) recalée(s) dans le calendrier.")
        if action == "publier":
            if _publier(request, promo):
                return redirect("agenda:promotions")
            return redirect("agenda:fiche_vitrine", promo_id=promo.pk)
        messages.success(request, f"Session « {promo.nom} » enregistrée."
                         + (" Le site est à jour." if promo.publiee_vitrine else ""))
        return redirect("agenda:promotions")
    return _page_session(request, form, promo)


@formateur_requis
def generer_promo(request, promo_id):
    promo = get_object_or_404(promotions_visibles(request.user), pk=promo_id)
    if not pilote_promotion(request.user, promo):  # calendrier : admin ou formateur référent
        raise PermissionDenied
    if request.method == "POST":
        n = generer_agenda(promo)
        if n:
            messages.success(request, f"{n} séances datées générées pour « {promo.nom} ».")
        else:
            messages.info(request, "Le calendrier est déjà généré (aucune séance à ajouter).")
    return redirect("agenda:promotions")


@formateur_requis
def presences(request, ev_id):
    """Feuille de présence d'une séance datée, ouverte dès son début : un statut par apprenant
    confirmé ou en cours (et ceux déjà pointés, pour l'historique). L'enregistrer réalise la séance."""
    ev = get_object_or_404(Evenement.objects.filter(q_interventions(request.user))
                           .select_related("promotion", "seance", "seance__module"), pk=ev_id)
    if ev.statut == Evenement.Statut.ANNULE or ev.date_debut > timezone.now():
        messages.info(request, "Séance annulée : pas de présences." if ev.statut == Evenement.Statut.ANNULE
                      else "La feuille de présence s'ouvre au début de la séance.")
        return redirect("agenda:planning", promo_id=ev.promotion_id)
    inscriptions = (ev.promotion.inscriptions
                    .filter(Q(pk__in=inscriptions_a_pointer(ev.promotion)) | Q(presences__evenement=ev))
                    .distinct().select_related("apprenant")
                    .order_by("apprenant__last_name", "apprenant__first_name", "apprenant__username"))
    existantes = {p.inscription_id: p for p in ev.presences.all()}

    if request.method == "POST":
        for insc in inscriptions:
            statut = request.POST.get(f"statut_{insc.id}")
            if statut not in Presence.Statut.values:
                continue
            present = statut in (Presence.Statut.PRESENT, Presence.Statut.RETARD)
            Presence.objects.update_or_create(
                inscription=insc, evenement=ev,
                defaults={"seance": ev.seance, "statut": statut,
                          "duree_realisee_h": ev.duree_h if present else Decimal("0")})
        if ev.statut in STATUTS_A_POINTER and not presences_manquantes(ev):
            ev.statut = Evenement.Statut.REALISE
            ev.save(update_fields=["statut"])
        messages.success(request, "Présences enregistrées." + (" Séance réalisée." if ev.statut == Evenement.Statut.REALISE else ""))
        return redirect("agenda:planning", promo_id=ev.promotion_id)

    lignes = [{"inscription": i,
               "statut": existantes[i.id].statut if i.id in existantes else Presence.Statut.PRESENT}
              for i in inscriptions]
    return render(request, "agenda/presences.html",
                  {"evenement": ev, "lignes": lignes, "statuts": Presence.Statut.choices})


@formateur_requis
def synchroniser(request, promo_id):
    promo = get_object_or_404(promotions_visibles(request.user), pk=promo_id)
    if not pilote_promotion(request.user, promo):
        raise PermissionDenied
    if request.method == "POST":
        recales, crees = synchroniser_agenda(promo)
        messages.success(request, f"Paramétrage appliqué : {recales} séance(s) recalée(s), {crees} ajoutée(s).")
    return redirect("agenda:planning", promo_id=promo.pk)


@admin_requis
def affectations(request, promo_id):
    """L'admin autorise des formateurs à intervenir dans la promotion, module par module."""
    promo = get_object_or_404(Promotion.objects.select_related("formation", "formateur"), pk=promo_id)
    modules = list(promo.formation.modules.order_by("ordre"))
    formateurs = (get_user_model().objects.filter(profil__role=FORMATEUR, is_active=True, is_superuser=False)
                  .order_by("first_name", "last_name", "username"))
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "retirer":
            a = get_object_or_404(promo.affectations, pk=request.POST.get("affectation"))
            a.delete()
            messages.success(request, f"{a.formateur.get_full_name() or a.formateur} n'intervient plus dans « {promo.nom} ».")
        else:
            formateur = formateurs.filter(pk=request.POST.get("formateur") or None).first()
            tous = bool(request.POST.get("tous_les_modules"))
            choisis = [m for m in modules if str(m.pk) in request.POST.getlist("modules")]
            if not formateur:
                messages.error(request, "Choisis un formateur.")
            elif not tous and not choisis:
                messages.error(request, "Coche au moins un module, ou « Tous les modules ».")
            else:
                a, cree = Affectation.objects.get_or_create(promotion=promo, formateur=formateur)
                a.tous_les_modules, a.accordee_par = tous, request.user
                a.save()
                a.modules.set([] if tous else choisis)
                portee = "tous les modules" if tous else ", ".join(m.code for m in choisis)
                if cree:
                    notifier([formateur], titre=f"Nouvelle intervention : {promo.nom}",
                             message=f"L'administration t'a affecté à « {promo.nom} » ({portee}).",
                             type=Notification.Type.INFO, expediteur=request.user,
                             module=choisis[0] if len(choisis) == 1 else None,
                             lien=reverse("agenda:planning", args=[promo.pk]))
                messages.success(request, f"{formateur.get_full_name() or formateur} : {portee}.")
        return redirect("agenda:affectations", promo_id=promo.pk)
    liste = list(promo.affectations.select_related("formateur").prefetch_related("modules")
                 .order_by("formateur__first_name", "formateur__username"))
    for a in liste:
        a.ids = {m.pk for m in a.modules.all()}
    return render(request, "agenda/affectations.html", {
        "promotion": promo, "modules": modules, "affectations": liste,
        "disponibles": formateurs.exclude(pk__in=[a.formateur_id for a in liste])
                                 .exclude(pk=promo.formateur_id or 0)})


@formateur_requis
def acces_contenus(request, promo_id):
    """Ouverture des modules d'une promotion aux apprenants : automatique (calendrier), ouvert ou fermé.
    Décision réservée à l'administration ; le formateur consulte l'état des modules qu'il enseigne."""
    from apps.formation.acces import etats_promotion
    promo = get_object_or_404(promotions_visibles(request.user).select_related("formation"), pk=promo_id)
    modules = list(promo.formation.modules.order_by("ordre"))
    admin = est_admin(request.user)
    if not admin:
        from apps.core.permissions import modules_gerables
        autorises = set(modules_gerables(request.user).values_list("pk", flat=True))
        modules = [m for m in modules if m.id in autorises]
    if request.method == "POST":
        if not admin:
            raise PermissionDenied
        if request.POST.get("action") == "mode":
            promo.ouverture_auto = bool(request.POST.get("ouverture_auto"))
            promo.save(update_fields=["ouverture_auto"])
            messages.success(request, "Ouverture automatique " + ("activée." if promo.ouverture_auto else "désactivée."))
        else:
            module = get_object_or_404(promo.formation.modules, pk=request.POST.get("module"))
            etat = request.POST.get("etat")
            if etat not in AccesModule.Etat.values:
                messages.error(request, "État inconnu.")
                return redirect("agenda:acces", promo_id=promo.pk)
            avant = etats_promotion(promo, [module])[module.id].ouvert
            AccesModule.objects.update_or_create(promotion=promo, module=module,
                                                 defaults={"etat": etat, "modifie_par": request.user})
            apres = etats_promotion(promo, [module])[module.id].ouvert
            if apres and not avant and request.POST.get("prevenir"):
                notifier(apprenants_de(promo), titre=f"Nouveau module disponible : {module.code}",
                         message=f"« {module.titre} » est maintenant accessible dans ton cours.",
                         type=Notification.Type.INFO, expediteur=request.user, module=module)
            messages.success(request, f"{module.code} : {'ouvert' if apres else 'fermé'} pour {promo.nom}.")
        return redirect("agenda:acces", promo_id=promo.pk)
    etats = etats_promotion(promo, modules)
    decisions = dict(promo.acces_modules.values_list("module_id", "etat"))
    lignes = [{"module": m, "acces": etats[m.id], "decision": decisions.get(m.id, AccesModule.Etat.AUTO)}
              for m in modules]
    return render(request, "agenda/acces.html", {
        "promotion": promo, "lignes": lignes, "etats_choix": AccesModule.Etat.choices, "peut_decider": admin,
        "nb_ouverts": sum(1 for l in lignes if l["acces"].ouvert)})


@formateur_requis
def pilotage(request, promo_id):
    """Cycle de vie de la promotion : statut, conditions du passage suivant, inscriptions, journal.
    Les décisions (passages, paiements, confirmations) sont réservées à l'administration."""
    from apps.evaluation.models import Inscription, JournalStatut
    from . import workflow
    promo = get_object_or_404(promotions_visibles(request.user).select_related("formation", "formateur"), pk=promo_id)
    admin = est_admin(request.user)
    if request.method == "POST":
        if not admin:
            raise PermissionDenied
        action, motif = request.POST.get("action"), (request.POST.get("motif") or "").strip()
        try:
            if action == "promotion":
                cible = request.POST.get("cible")
                if cible not in Promotion.Statut.values:
                    raise workflow.TransitionRefusee(["Statut inconnu."])
                messages.success(request, workflow.changer_statut_promotion(promo, cible, request.user, motif))
            elif action == "desarchiver":
                messages.success(request, workflow.desarchiver(promo, request.user, motif))
            elif action in ("inscription", "paiement"):
                insc = get_object_or_404(promo.inscriptions.select_related("apprenant"), pk=request.POST.get("inscription"))
                nom = insc.apprenant.get_full_name() or insc.apprenant.username
                if action == "paiement":
                    paiement = request.POST.get("paiement")
                    if paiement not in Inscription.Paiement.values:
                        raise workflow.TransitionRefusee(["Paiement inconnu."])
                    insc.paiement = paiement
                    insc.save(update_fields=["paiement"])
                    messages.success(request, f"{nom} : paiement « {insc.get_paiement_display()} ».")
                else:
                    cible = request.POST.get("cible")
                    if cible not in Inscription.Statut.values:
                        raise workflow.TransitionRefusee(["Statut inconnu."])
                    workflow.changer_statut_inscription(insc, cible, request.user, motif)
                    messages.success(request, f"{nom} : {insc.get_statut_display()}.")
        except workflow.TransitionRefusee as refus:
            messages.error(request, "Passage refusé : " + " ; ".join(refus.manques))
        return redirect("agenda:pilotage", promo_id=promo.pk)

    inscriptions = list(promo.inscriptions.select_related("apprenant").order_by(
        "apprenant__last_name", "apprenant__first_name", "apprenant__username"))
    for i in inscriptions:
        i.actions = workflow.actions_inscription(i) if admin else []
        i.paiement_modifiable = i.statut in (Inscription.Statut.ADMISE, Inscription.Statut.CONFIRMEE)
    journal = list(JournalStatut.objects.filter(promotion=promo).select_related("par", "inscription__apprenant")[:40])
    for j in journal:
        libelles = dict(Inscription.Statut.choices if j.inscription_id else Promotion.Statut.choices)
        j.libelle_de, j.libelle_vers = libelles.get(j.de, j.de), libelles.get(j.vers, j.vers)
        j.auteur = (j.par.get_full_name() or j.par.username) if j.par else "automatique"
    etapes = workflow.ETAPES_PROMOTION
    rang = etapes.index(promo.statut)
    compte = {s: sum(1 for i in inscriptions if i.statut == s) for s in Inscription.Statut.values}
    return render(request, "agenda/pilotage.html", {
        "promotion": promo, "peut_decider": admin,
        "etapes": [{"valeur": s, "libelle": Promotion.Statut(s).label, "faite": n < rang, "courante": n == rang}
                   for n, s in enumerate(etapes)],
        "actions": workflow.actions_promotion(promo),
        "inscriptions": inscriptions, "compte": compte, "paiements": Inscription.Paiement.choices,
        "journal": journal,
    })
