import datetime as dt
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from apps.core.permissions import (APPRENANT, FORMATEUR, formateur_requis, est_admin,
                                   promotions_visibles, role_de)
from apps.evaluation.models import Presence
from apps.evaluation.utils import inscription_courante
from .forms import AnnonceForm, FicheVitrineForm
from .models import AccesModule, Annonce, Promotion, Evenement, Notification
from .services import apprenants_de, notifier, generer_agenda, synchroniser_agenda


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
        qs = Evenement.objects.filter(promotion__in=promotions_visibles(request.user),
                                      promotion__active=True)
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
    liste = request.user.notifications.select_related("evenement", "evenement__seance", "expediteur")[:50]
    return render(request, "agenda/notifications.html", {"notifications": liste})


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
                 expediteur=request.user, annonce=annonce)
        messages.success(request, f"Notification envoyée à {annonce.nb_destinataires} personne(s).")
        return redirect("agenda:envoyer")
    historique = Annonce.objects.select_related("expediteur", "promotion")
    if not est_admin(request.user):
        historique = historique.filter(expediteur=request.user)
    return render(request, "agenda/envoyer.html", {"form": form, "historique": historique[:30]})


@formateur_requis
def planning(request, promo_id):
    promo = get_object_or_404(promotions_visibles(request.user), pk=promo_id)
    evenements = (promo.evenements.select_related("seance", "seance__module")
                  .annotate(nb_presences=Count("presences")).order_by("date_debut"))
    return render(request, "agenda/planning.html",
                  {"promotion": promo, "evenements": evenements,
                   "nb_apprenants": promo.inscriptions.count(),
                   "statuts": Evenement.Statut.choices})


@formateur_requis
def evenement_action(request, ev_id):
    ev = get_object_or_404(Evenement, pk=ev_id, promotion__in=promotions_visibles(request.user))
    if request.method != "POST":
        return redirect("agenda:planning", promo_id=ev.promotion_id)
    action = request.POST.get("action")

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
            if request.POST.get("decaler_suite"):
                suivants = ev.promotion.evenements.filter(date_debut__gt=ancienne).exclude(pk=ev.pk)
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
                 message=f"Rendez-vous le {heure} — {ev.get_mode_display()}"
                         + (f" · {ev.lieu}" if ev.lieu else ""),
                 evenement=ev, type=Notification.Type.AGENDA, expediteur=request.user)
        messages.success(request, "Apprenant(s) notifié(s) (in-app + e-mail si configuré).")

    return redirect("agenda:planning", promo_id=ev.promotion_id)


@formateur_requis
def promotions(request):
    """Admin : crée les promotions et affecte les formateurs. Formateur : ses promotions."""
    from apps.formation.models import Formation
    admin = est_admin(request.user)
    formateurs = (get_user_model().objects
                   .filter(profil__role__in=[FORMATEUR, "admin"]).order_by("first_name", "username"))
    if request.method == "POST":
        if not admin:
            raise PermissionDenied
        if request.POST.get("action") == "affecter":
            promo = get_object_or_404(Promotion, pk=request.POST.get("promotion"))
            promo.formateur = formateurs.filter(pk=request.POST.get("formateur") or None).first()
            promo.save(update_fields=["formateur"])
            messages.success(request, f"Formateur de « {promo.nom} » mis à jour.")
            return redirect("agenda:promotions")
        nom = (request.POST.get("nom") or "").strip()
        formation_id = request.POST.get("formation")
        date_debut = request.POST.get("date_debut")
        if nom and formation_id and date_debut:
            Promotion.objects.create(
                nom=nom, formation_id=formation_id, date_debut=date_debut,
                code_vitrine=slugify(request.POST.get("code_vitrine", ""))[:100],
                formateur=formateurs.filter(pk=request.POST.get("formateur") or None).first())
            messages.success(request, "Promotion créée. Tu peux générer son calendrier.")
        else:
            messages.error(request, "Renseigne le nom, la formation et la date de début.")
        return redirect("agenda:promotions")
    liste = (promotions_visibles(request.user).select_related("formation", "formateur")
             .annotate(nb_evenements=Count("evenements", distinct=True),
                       nb_apprenants=Count("inscriptions", distinct=True))
             .order_by("-date_debut"))
    return render(request, "agenda/promotions.html", {
        "promotions": liste, "formations": Formation.objects.filter(active=True),
        "formateurs": formateurs, "peut_gerer": admin,
    })


@formateur_requis
def fiche_vitrine(request, promo_id):
    """Admin : ce que le site vitrine affiche de la promotion (API publique /api/sessions/)."""
    if not est_admin(request.user):
        raise PermissionDenied
    promo = get_object_or_404(Promotion.objects.select_related("formation"), pk=promo_id)
    form = FicheVitrineForm(request.POST or None, instance=promo)
    if request.method == "POST" and form.is_valid():
        promo = form.save()
        if promo.publiee_vitrine:
            messages.success(request, f"« {promo.nom} » est publiée sur le site vitrine "
                                      f"({promo.places_restantes} place(s) disponible(s)).")
        else:
            messages.success(request, f"Fiche vitrine de « {promo.nom} » enregistrée (non publiée).")
        return redirect("agenda:promotions")
    return render(request, "agenda/fiche_vitrine.html", {"promo": promo, "form": form})


@formateur_requis
def generer_promo(request, promo_id):
    promo = get_object_or_404(promotions_visibles(request.user), pk=promo_id)
    if request.method == "POST":
        n = generer_agenda(promo)
        if n:
            messages.success(request, f"{n} séances datées générées pour « {promo.nom} ».")
        else:
            messages.info(request, "Le calendrier est déjà généré (aucune séance à ajouter).")
    return redirect("agenda:promotions")


@formateur_requis
def presences(request, ev_id):
    """Feuille de présence d'une séance datée : un statut par apprenant de la promotion."""
    ev = get_object_or_404(Evenement.objects.select_related("promotion", "seance", "seance__module"),
                           pk=ev_id, promotion__in=promotions_visibles(request.user))
    inscriptions = ev.promotion.inscriptions.select_related("apprenant").order_by(
        "apprenant__last_name", "apprenant__first_name", "apprenant__username")
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
        if ev.statut in (Evenement.Statut.PLANIFIE, Evenement.Statut.CONFIRME):
            ev.statut = Evenement.Statut.REALISE
            ev.save(update_fields=["statut"])
        messages.success(request, "Présences enregistrées.")
        return redirect("agenda:planning", promo_id=ev.promotion_id)

    lignes = [{"inscription": i,
               "statut": existantes[i.id].statut if i.id in existantes else Presence.Statut.PRESENT}
              for i in inscriptions]
    return render(request, "agenda/presences.html",
                  {"evenement": ev, "lignes": lignes, "statuts": Presence.Statut.choices})


@formateur_requis
def synchroniser(request, promo_id):
    promo = get_object_or_404(promotions_visibles(request.user), pk=promo_id)
    if request.method == "POST":
        recales, crees = synchroniser_agenda(promo)
        messages.success(request, f"Paramétrage appliqué : {recales} séance(s) recalée(s), {crees} ajoutée(s).")
    return redirect("agenda:planning", promo_id=promo.pk)


@formateur_requis
def acces_contenus(request, promo_id):
    """Ouverture des modules d'une promotion : automatique (calendrier), ouvert ou fermé."""
    from apps.formation.acces import etats_promotion
    promo = get_object_or_404(promotions_visibles(request.user).select_related("formation"), pk=promo_id)
    modules = list(promo.formation.modules.order_by("ordre"))
    if request.method == "POST":
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
                         type=Notification.Type.INFO, expediteur=request.user)
            messages.success(request, f"{module.code} : {'ouvert' if apres else 'fermé'} pour {promo.nom}.")
        return redirect("agenda:acces", promo_id=promo.pk)
    etats = etats_promotion(promo, modules)
    decisions = dict(promo.acces_modules.values_list("module_id", "etat"))
    lignes = [{"module": m, "acces": etats[m.id], "decision": decisions.get(m.id, AccesModule.Etat.AUTO)}
              for m in modules]
    return render(request, "agenda/acces.html", {
        "promotion": promo, "lignes": lignes, "etats_choix": AccesModule.Etat.choices,
        "nb_ouverts": sum(1 for l in lignes if l["acces"].ouvert)})
