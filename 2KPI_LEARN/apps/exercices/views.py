from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from apps.core.permissions import APPRENANT, formateur_requis, modules_gerables, role_de
from apps.evaluation.utils import inscription_courante
from . import services
from .correction import choix_coches, enregistrer_copie, resultat, resultat_visible
from .forms import choix_formset, CorrectionSeuleForm, ExerciceForm, PlanificationForm, QuestionForm
from .models import Choix, Copie, Exercice, Planification, Question


@login_required
def liste(request):
    if role_de(request.user) == APPRENANT:
        return _liste_apprenant(request)
    return _liste_formateur(request)


@formateur_requis
def _liste_formateur(request):
    modules = modules_gerables(request.user)
    form = ExerciceForm(request.POST or None, modules=modules)
    if request.method == "POST" and form.is_valid():
        ex = form.save(commit=False)
        ex.auteur = request.user
        ex.save()
        messages.success(request, "Exercice créé : ajoute ses questions.")
        return redirect("exercices:exercice", pk=ex.pk)
    exercices = (services.exercices_gerables(request.user).select_related("module__formation")
                 .prefetch_related("questions", "planifications__promotion"))
    return render(request, "exercices/liste_formateur.html", {"form": form, "exercices": exercices,
                                                             "ouvrir_formulaire": request.method == "POST"})


def _liste_apprenant(request):
    insc = inscription_courante(request.user)
    lignes = []
    for planif in services.planifications_apprenant(insc):
        copie = Copie.objects.filter(planification=planif, inscription=insc).prefetch_related("reponses").first()
        lignes.append({"planif": planif, "copie": copie,
                       "resultat": resultat(planif, copie) if resultat_visible(planif, copie) else None})
    return render(request, "exercices/liste_apprenant.html", {"lignes": lignes, "inscription": insc})


# ---------- Formateur : composer ----------

def _exercice_gere(request, pk):
    ex = get_object_or_404(Exercice.objects.select_related("module__formation"), pk=pk)
    if not modules_gerables(request.user).filter(pk=ex.module_id).exists():
        raise Http404
    return ex


@formateur_requis
def exercice(request, pk):
    ex = _exercice_gere(request, pk)
    form = ExerciceForm(request.POST if request.POST.get("quoi") == "exercice" else None, instance=ex,
                        modules=modules_gerables(request.user))
    promos = services.promotions_planifiables(request.user, ex)
    planif_form = PlanificationForm(request.POST if request.POST.get("quoi") == "planifier" else None,
                                    instance=Planification(exercice=ex), promotions=promos)
    if request.method == "POST":
        quoi = request.POST.get("quoi")
        if quoi == "exercice" and form.is_valid():
            form.save()
            messages.success(request, "Exercice enregistré.")
            return redirect("exercices:exercice", pk=ex.pk)
        if quoi == "planifier" and planif_form.is_valid():
            if not ex.questions.exists():
                messages.error(request, "Ajoute au moins une question avant de planifier l'exercice.")
            else:
                planif = planif_form.save(commit=False)
                planif.cree_par = request.user
                planif.save()
                services.annoncer(planif, request.user)
                messages.success(request, f"Exercice planifié pour « {planif.promotion.nom} » ; les apprenants sont prévenus.")
                return redirect("exercices:exercice", pk=ex.pk)
        if quoi == "supprimer" and not ex.verrouille:
            ex.delete()
            messages.success(request, "Exercice supprimé.")
            return redirect("exercices:liste")
        if quoi == "deplanifier":
            planif = get_object_or_404(ex.planifications, pk=request.POST.get("planification"))
            if planif.copies.exists():
                messages.error(request, "Des apprenants ont déjà répondu : la planification ne peut plus être retirée.")
            else:
                planif.delete()
                messages.success(request, "Planification retirée.")
            return redirect("exercices:exercice", pk=ex.pk)
    planifs = [{"planif": p, "nb_copies": p.copies.count(), "peut_suivre": services.peut_suivre(request.user, p)}
               for p in ex.planifications.select_related("promotion")]
    return render(request, "exercices/exercice.html", {
        "exercice": ex, "form": form, "planif_form": planif_form, "planifs": planifs,
        "questions": ex.questions.prefetch_related("choix"), "verrouille": ex.verrouille})


@formateur_requis
def question(request, exercice_pk, pk=None):
    ex = _exercice_gere(request, exercice_pk)
    q = get_object_or_404(ex.questions, pk=pk) if pk else Question(exercice=ex, ordre=ex.questions.count() + 1)
    data = request.POST if request.method == "POST" else None
    if ex.verrouille:
        if not q.pk:
            messages.error(request, "Des apprenants ont déjà répondu : on ne peut plus ajouter de question.")
            return redirect("exercices:exercice", pk=ex.pk)
        form = CorrectionSeuleForm(data, instance=q)
        if request.method == "POST" and form.is_valid():
            form.save()
            messages.success(request, "Correction enregistrée.")
            return redirect("exercices:exercice", pk=ex.pk)
        return render(request, "exercices/question.html", {"exercice": ex, "question": q, "form": form,
                                                          "verrouille": True})
    form = QuestionForm(data, instance=q)
    formset = choix_formset(q)(data, instance=q, prefix="choix")
    erreurs = []
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        t = form.cleaned_data["type"]
        choix = [f for f in formset.forms if f.cleaned_data.get("texte") and not f.cleaned_data.get("DELETE")]
        if t == Question.Type.QCM and (len(choix) < 2 or not any(f.cleaned_data.get("correct") for f in choix)):
            erreurs.append("Un choix multiple demande au moins deux propositions, dont au moins une bonne réponse.")
        if not erreurs:
            with transaction.atomic():
                q = form.save()
                if t == Question.Type.QCM:
                    formset.instance = q
                    formset.save()
                    gardes = [f.instance for f in formset.forms  # ordre de la page, ajouts compris
                              if f.instance.pk and f not in formset.deleted_forms]
                    for n, c in enumerate(gardes, 1):
                        c.ordre = n
                        c.save(update_fields=["ordre"])
                elif t == Question.Type.VF:
                    vrai = form.cleaned_data["bonne_reponse_vf"] == "vrai"
                    q.choix.exclude(texte__in=["Vrai", "Faux"]).delete()
                    Choix.objects.update_or_create(question=q, texte="Vrai", defaults={"correct": vrai, "ordre": 1})
                    Choix.objects.update_or_create(question=q, texte="Faux", defaults={"correct": not vrai, "ordre": 2})
                else:
                    q.choix.all().delete()
            messages.success(request, "Question enregistrée.")
            if request.POST.get("suite"):
                return redirect("exercices:question_ajouter", exercice_pk=ex.pk)
            return redirect("exercices:exercice", pk=ex.pk)
    return render(request, "exercices/question.html", {
        "exercice": ex, "question": q, "form": form, "formset": formset, "erreurs": erreurs, "verrouille": False})


@formateur_requis
def question_supprimer(request, exercice_pk, pk):
    ex = _exercice_gere(request, exercice_pk)
    if request.method == "POST":
        if ex.verrouille:
            messages.error(request, "Des apprenants ont déjà répondu : les questions sont figées.")
        else:
            get_object_or_404(ex.questions, pk=pk).delete()
            messages.success(request, "Question supprimée.")
    return redirect("exercices:exercice", pk=ex.pk)


# ---------- Formateur : suivre et corriger ----------

def _planif_suivie(request, pk):
    planif = get_object_or_404(Planification.objects.select_related("exercice__module", "promotion"), pk=pk)
    if role_de(request.user) == APPRENANT or not services.peut_suivre(request.user, planif):
        raise Http404
    return planif


@formateur_requis
def suivi(request, pk):
    from apps.agenda.services import inscriptions_a_pointer
    planif = _planif_suivie(request, pk)
    copies = {c.inscription_id: c for c in planif.copies.prefetch_related("reponses")}
    inscriptions = (inscriptions_a_pointer(planif.promotion) | planif.promotion.inscriptions.filter(pk__in=copies)) \
        .distinct().select_related("apprenant").order_by("apprenant__last_name", "apprenant__first_name")
    lignes = [{"inscription": i, "copie": copies.get(i.pk), "resultat": resultat(planif, copies.get(i.pk)) if i.pk in copies else None}
              for i in inscriptions]
    notes = [l["resultat"]["note_sur_20"] for l in lignes if l["resultat"] and l["resultat"]["complet"]]
    return render(request, "exercices/suivi.html", {
        "planif": planif, "lignes": lignes, "nb_rendues": len(copies),
        "a_corriger": sum(1 for l in lignes if l["resultat"] and not l["resultat"]["complet"]),
        "moyenne": (sum(notes) / len(notes)).quantize(Decimal("0.01")) if notes else None})


@formateur_requis
def corriger(request, pk):
    copie = get_object_or_404(Copie.objects.select_related("planification__exercice__module", "planification__promotion",
                                                           "inscription__apprenant"), pk=pk)
    planif = _planif_suivie(request, copie.planification_id)
    reponses = {r.question_id: r for r in copie.reponses.all()}
    questions = list(planif.exercice.questions.prefetch_related("choix"))
    if request.method == "POST":
        if not planif.termine:
            messages.error(request, "La correction s'ouvre à la date limite : l'apprenant peut encore modifier ses réponses.")
            return redirect("exercices:corriger", pk=copie.pk)
        erreurs = []
        with transaction.atomic():
            for q in questions:
                r = reponses.get(q.pk)
                if r is None:
                    continue
                r.commentaire = (request.POST.get(f"commentaire_{q.pk}") or "").strip()
                if q.type == Question.Type.REDACTION and r.valeur.strip():
                    brut = (request.POST.get(f"points_{q.pk}") or "").strip().replace(",", ".")
                    try:
                        points = Decimal(brut) if brut else None
                        valide = points is None or 0 <= points <= q.points
                    except InvalidOperation:
                        valide = False
                    if not valide:
                        erreurs.append(f"Question {questions.index(q) + 1} : note entre 0 et {q.points:g}")
                        continue
                    r.points = points
                r.save(update_fields=["commentaire", "points"])
        if erreurs:
            messages.error(request, "À vérifier : " + " ; ".join(erreurs) + ".")
        else:
            messages.success(request, "Correction enregistrée." + (" L'apprenant est prévenu de son résultat."
                                                                   if services.notifier_resultat(copie) else ""))
        return redirect("exercices:corriger", pk=copie.pk)
    items = [{"q": q, "r": reponses.get(q.pk), "coches": choix_coches(reponses[q.pk].valeur) if q.pk in reponses else set()}
             for q in questions]
    return render(request, "exercices/corriger.html", {"copie": copie, "planif": planif, "items": items,
                                                       "resultat": resultat(planif, copie)})


# ---------- Apprenant : s'exercer, puis consulter le résultat ----------

def _planif_apprenant(request, pk):
    insc = inscription_courante(request.user)
    planif = get_object_or_404(services.planifications_apprenant(insc), pk=pk)
    if not insc.est_active and not planif.termine:
        raise PermissionDenied
    return insc, planif


@login_required
def faire(request, pk):
    if role_de(request.user) != APPRENANT:
        raise Http404
    insc, planif = _planif_apprenant(request, pk)
    if planif.termine:
        return redirect("exercices:resultat", pk=planif.pk)
    copie = Copie.objects.filter(planification=planif, inscription=insc).prefetch_related("reponses").first()
    if request.method == "POST" and planif.ouvert:
        valeurs = {}
        for q in planif.exercice.questions.all():
            if q.type in (Question.Type.QCM, Question.Type.VF):
                valeurs[q.pk] = ",".join(v for v in request.POST.getlist(f"q{q.pk}") if v.isdigit())
            else:
                valeurs[q.pk] = request.POST.get(f"q{q.pk}", "")[:5000]
        enregistrer_copie(planif, insc, valeurs)
        messages.success(request, "Réponses enregistrées. Tu peux les modifier jusqu'à la date limite ; "
                                  "le résultat et la correction seront visibles ensuite.")
        return redirect("exercices:faire", pk=planif.pk)
    valeurs = {r.question_id: r.valeur for r in copie.reponses.all()} if copie else {}
    items = [{"q": q, "valeur": valeurs.get(q.pk, ""), "coches": choix_coches(valeurs.get(q.pk, ""))}
             for q in planif.exercice.questions.prefetch_related("choix")]
    return render(request, "exercices/faire.html", {"planif": planif, "items": items, "copie": copie})


@login_required
def resultat_apprenant(request, pk):
    if role_de(request.user) != APPRENANT:
        raise Http404
    insc, planif = _planif_apprenant(request, pk)
    if not planif.termine:
        return redirect("exercices:faire", pk=planif.pk)
    copie = Copie.objects.filter(planification=planif, inscription=insc).prefetch_related("reponses").first()
    visible = resultat_visible(planif, copie)
    reponses = {r.question_id: r for r in copie.reponses.all()} if copie else {}
    items = [{"q": q, "r": reponses.get(q.pk), "coches": choix_coches(reponses[q.pk].valeur) if q.pk in reponses else set()}
             for q in planif.exercice.questions.prefetch_related("choix")] if visible else []
    return render(request, "exercices/resultat.html", {
        "planif": planif, "copie": copie, "visible": visible, "items": items,
        "resultat": resultat(planif, copie) if visible else None})
