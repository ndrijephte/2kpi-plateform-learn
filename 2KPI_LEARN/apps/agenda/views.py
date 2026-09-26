import datetime as dt
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from apps.evaluation.utils import inscription_courante
from .models import Promotion, Evenement, Notification
from .services import apprenants_de, notifier
from .utils import est_formateur


def _grouper_par_semaine(evenements):
    groupes = {}
    for ev in evenements:
        an, sem, _ = ev.date_debut.isocalendar()
        groupes.setdefault((an, sem), []).append(ev)
    return [{"label": f"Semaine {sem}", "annee": an, "evenements": evs}
            for (an, sem), evs in sorted(groupes.items())]


@login_required
def mon_agenda(request):
    insc = inscription_courante(request.user)
    promo = insc.promotion if insc else None
    evenements = list(promo.evenements.select_related("seance", "seance__module")) if promo else []
    maintenant = timezone.now()
    prochaine = next((e for e in evenements
                      if e.date_debut >= maintenant and e.statut != Evenement.Statut.ANNULE), None)
    return render(request, "agenda/mon_agenda.html", {
        "promotion": promo, "semaines": _grouper_par_semaine(evenements),
        "prochaine": prochaine, "maintenant": maintenant,
    })


@login_required
def notifications(request):
    if request.method == "POST":
        request.user.notifications.filter(lu=False).update(lu=True)
        return redirect("agenda:notifications")
    liste = request.user.notifications.select_related("evenement")[:50]
    return render(request, "agenda/notifications.html", {"notifications": liste})


@login_required
@user_passes_test(est_formateur)
def planning(request, promo_id):
    promo = get_object_or_404(Promotion, pk=promo_id)
    evenements = promo.evenements.select_related("seance", "seance__module")
    return render(request, "agenda/planning.html",
                  {"promotion": promo, "evenements": evenements,
                   "statuts": Evenement.Statut.choices})


@login_required
@user_passes_test(est_formateur)
def evenement_action(request, ev_id):
    ev = get_object_or_404(Evenement, pk=ev_id)
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
                 evenement=ev, type=Notification.Type.AGENDA)
        messages.success(request, "Apprenant(s) notifié(s) (in-app + e-mail si configuré).")

    return redirect("agenda:planning", promo_id=ev.promotion_id)
