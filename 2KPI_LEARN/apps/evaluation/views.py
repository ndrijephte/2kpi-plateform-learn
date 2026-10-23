import random
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Max, Q
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from apps.agenda.models import Notification
from apps.agenda.services import notifier
from apps.core.permissions import (ADMIN, APPRENANT, formateur_requis, interventions, promotions_visibles,
                                   q_interventions, role_de, role_requis)
from .models import Inscription, Livrable, Quiz, TentativeQuiz
from apps.formation.acces import acces_module
from .grading import corriger
from .utils import inscription_courante


def _prepare_questions(quiz):
    """Structure d'affichage par question (choix, appariement mélangé)."""
    data = []
    for q in quiz.questions.all().prefetch_related("choix"):
        item = {"q": q, "type": q.type}
        if q.type in ("qcm", "vf"):
            item["choix"] = list(q.choix.all())
            item["multi"] = q.type == "qcm" and sum(1 for c in q.choix.all() if c.correct) > 1
        elif q.type == "appariement":
            pairs, droites = [], []
            for c in q.choix.all():
                g = c.texte.split("->", 1)[0].strip()
                d = c.texte.split("->", 1)[1].strip() if "->" in c.texte else ""
                pairs.append({"cid": c.id, "gauche": g})
                droites.append(d)
            random.shuffle(droites)
            item["pairs"] = pairs
            item["droites"] = droites
        data.append(item)
    return data


@role_requis(APPRENANT)
def quiz(request, quiz_id):
    """Seul un apprenant inscrit à la formation du quiz peut le passer."""
    quiz = get_object_or_404(Quiz.objects.select_related("module"), pk=quiz_id)
    insc = inscription_courante(request.user)
    if not insc or insc.formation_id != quiz.module.formation_id:
        raise PermissionDenied
    etat = acces_module(request.user, quiz.module)
    if not etat.ouvert:
        return render(request, "formation/verrouille.html", {"module": quiz.module, "etat": etat}, status=403)
    if request.method == "POST":
        score, bonnes, total, details = corriger(quiz, request.POST)
        TentativeQuiz.objects.create(inscription=insc, quiz=quiz, score=score)
        resultats = [{"q": q, "ok": ok} for q, ok in details]
        return render(request, "evaluation/quiz_result.html", {
            "quiz": quiz, "score": score, "bonnes": bonnes, "total": total, "resultats": resultats,
        })
    tentatives = TentativeQuiz.objects.filter(inscription=insc, quiz=quiz).order_by("-date")[:5]
    return render(request, "evaluation/quiz.html",
                  {"quiz": quiz, "questions": _prepare_questions(quiz), "tentatives": tentatives})


@formateur_requis
def quiz_resultats(request, quiz_id):
    """Résultats d'un quiz pour les apprenants des promotions pilotées."""
    quiz = get_object_or_404(Quiz.objects.select_related("module__formation"), pk=quiz_id)
    if not acces_module(request.user, quiz.module).ouvert:  # module non attribué au formateur
        raise PermissionDenied
    perimetre = interventions(request.user)  # promotions où ce module est attribué au formateur
    promos = (promotions_visibles(request.user) if perimetre is None else
              [pid for pid, modules in perimetre.items() if modules is None or quiz.module_id in modules])
    inscriptions = (Inscription.objects
                    .filter(promotion__in=promos, formation_id=quiz.module.formation_id)
                    .select_related("apprenant", "promotion")
                    .annotate(meilleur=Max("tentatives__score", filter=Q(tentatives__quiz=quiz)),
                              nb=Count("tentatives", filter=Q(tentatives__quiz=quiz)),
                              derniere=Max("tentatives__date", filter=Q(tentatives__quiz=quiz)))
                    .order_by("promotion__nom", "apprenant__last_name", "apprenant__first_name"))
    notes = [i.meilleur for i in inscriptions if i.meilleur is not None]
    return render(request, "evaluation/quiz_resultats.html", {
        "quiz": quiz, "inscriptions": inscriptions, "nb_questions": quiz.questions.count(),
        "passes": len(notes), "moyenne": round(sum(notes) / len(notes), 2) if notes else None,
    })


@formateur_requis
def livrables(request):
    """Livrables rendus des promotions pilotées : à corriger / corrigés."""
    promos = promotions_visibles(request.user)
    qs = (Livrable.objects.filter(q_interventions(request.user, promotion="inscription__promotion"), rendu=True)
          .select_related("inscription__apprenant", "inscription__promotion", "seance__module")
          .order_by("seance__module__ordre", "seance__ordre", "inscription__apprenant__last_name"))
    if request.method == "POST":
        livrable = get_object_or_404(qs, pk=request.POST.get("livrable"))
        brut = (request.POST.get("note") or "").replace(",", ".").strip()
        try:
            note = Decimal(brut)
        except InvalidOperation:
            note = None
        if note is None or not (0 <= note <= 20):
            messages.error(request, "La note doit être un nombre entre 0 et 20.")
        else:
            livrable.note_sur_20 = note.quantize(Decimal("0.1"))
            livrable.observations = (request.POST.get("observations") or "").strip()
            livrable.save(update_fields=["note_sur_20", "observations"])
            notifier([livrable.inscription.apprenant],
                     titre=f"Livrable corrigé : {livrable.seance.module.code}",
                     message=f"Note : {livrable.note_sur_20}/20"
                             + (f" — {livrable.observations}" if livrable.observations else ""),
                     type=Notification.Type.INFO, expediteur=request.user)
            messages.success(request, f"Note enregistrée pour {livrable.inscription.apprenant}.")
        return redirect(f"{request.path}?{request.GET.urlencode()}")

    filtre = request.GET.get("statut", "a_corriger")
    promo_id = request.GET.get("promotion", "")
    if promo_id.isdigit():
        qs = qs.filter(inscription__promotion_id=promo_id)
    nb_a_corriger = qs.filter(note_sur_20__isnull=True).count()
    if filtre == "a_corriger":
        qs = qs.filter(note_sur_20__isnull=True)
    elif filtre == "corriges":
        qs = qs.filter(note_sur_20__isnull=False)
    return render(request, "evaluation/livrables.html", {
        "livrables": qs, "filtre": filtre, "promotions": promos, "promo_id": promo_id,
        "nb_a_corriger": nb_a_corriger,
    })


@login_required
def livrable_fichier(request, pk):
    """Fichier d'un livrable : son auteur, un formateur autorisé sur ce module dans sa promotion, ou un admin."""
    l = get_object_or_404(Livrable.objects.select_related("inscription"), pk=pk)
    autorise = (l.inscription.apprenant_id == request.user.pk
                or role_de(request.user) == ADMIN
                or Livrable.objects.filter(q_interventions(request.user, promotion="inscription__promotion"),
                                           pk=l.pk).exists())
    if not autorise:
        raise PermissionDenied
    if not l.fichier:
        raise Http404
    try:
        return FileResponse(l.fichier.open("rb"), as_attachment=True, filename=l.fichier.name.rsplit("/", 1)[-1])
    except FileNotFoundError:
        raise Http404


# ---------- Auto-évaluation sur les objectifs des séances ----------

@role_requis(APPRENANT)
def mes_acquis(request):
    """L'apprenant retrouve toutes ses auto-évaluations (modules ouverts) et ce qu'il doit retravailler."""
    from apps.formation.acces import etats_modules
    from . import autoevaluation
    insc = inscription_courante(request.user)
    synthese = None
    if insc:
        etats = etats_modules(insc, insc.formation.modules.all())
        synthese = autoevaluation.synthese_apprenant(insc, [mid for mid, e in etats.items() if e.ouvert])
    filtre = request.GET.get("filtre", "")
    if synthese and filtre == "a_retravailler":
        synthese["seances"] = [s for s in synthese["seances"]
                               if any(not l["eval"] or not l["eval"].acquis for l in s["lignes"])]
    return render(request, "evaluation/mes_acquis.html", {
        "inscription": insc, "synthese": synthese, "filtre": filtre})


@formateur_requis
def autoevaluations(request, promo_id):
    """Synthèse des auto-évaluations d'une promotion, limitée aux séances des modules du formateur."""
    from apps.formation.models import Seance
    from . import autoevaluation
    promo = get_object_or_404(promotions_visibles(request.user).select_related("formation"), pk=promo_id)
    perimetre = interventions(request.user)
    seances = Seance.objects.filter(module__formation_id=promo.formation_id)
    if perimetre is not None and perimetre.get(promo.pk) is not None:
        seances = seances.filter(module_id__in=perimetre[promo.pk])
    modules = list(promo.formation.modules.filter(seances__in=seances).distinct().order_by("ordre"))
    module_id = request.GET.get("module", "")
    if module_id.isdigit():
        seances = seances.filter(module_id=module_id)
    if request.method == "POST":  # le formateur a répondu à une demande d'aide
        from .models import AutoEvaluation
        a = get_object_or_404(AutoEvaluation.objects.select_related("inscription__apprenant", "objectif__seance"),
                              pk=request.POST.get("autoevaluation"), inscription__promotion=promo,
                              objectif__seance__in=seances, besoin_aide=True)
        a.besoin_aide = False
        a.save(update_fields=["besoin_aide"])
        notifier([a.inscription.apprenant], titre="Ta demande d'aide a été prise en compte",
                 message=f"Objectif « {a.objectif} » : n'hésite pas à te réévaluer après l'échange avec ton formateur.",
                 type=Notification.Type.INFO, expediteur=request.user)
        messages.success(request, f"Demande de {a.inscription.apprenant.get_full_name() or a.inscription.apprenant} marquée comme traitée.")
        return redirect(f"{request.path}?{request.GET.urlencode()}")
    synthese = autoevaluation.synthese_promotion(promo, seances)
    if request.GET.get("filtre") == "aide":
        synthese["seances"] = [s for s in synthese["seances"] if s["aides"]]
    return render(request, "evaluation/autoevaluations.html", {
        "promotion": promo, "synthese": synthese, "modules": modules, "module_id": module_id,
        "filtre": request.GET.get("filtre", ""), "niveaux": autoevaluation.echelle()})


def _note(brut):
    """Note saisie (virgule acceptée) → Decimal ; '' → None ; ValueError hors de [0, 20]."""
    brut = (brut or "").strip().replace(",", ".")
    if not brut:
        return None
    try:
        note = Decimal(brut).quantize(Decimal("0.1"))
    except InvalidOperation:
        raise ValueError(brut)
    if not Decimal(0) <= note <= Decimal(20):
        raise ValueError(brut)
    return note


@formateur_requis
def evaluation_promotion(request, promo_id):
    """Prérequis des apprenants et évaluation finale (grille du projet, soutenance) d'une promotion.
    Saisie : administration et formateur référent ; les autres formateurs de la promotion consultent."""
    from django.db import transaction
    from apps.core.permissions import pilote_promotion
    from apps.tableau_bord.services import synthese
    from . import grille
    from .models import PrerequisInscription, Soutenance
    promo = get_object_or_404(promotions_visibles(request.user).select_related("formation"), pk=promo_id)
    formation = promo.formation
    peut_saisir = pilote_promotion(request.user, promo)
    S = Inscription.Statut
    ordre = ("apprenant__last_name", "apprenant__first_name", "apprenant__username")
    a_preparer = list(promo.inscriptions.filter(statut__in=[S.ADMISE, S.CONFIRMEE, S.EN_COURS])
                      .select_related("apprenant", "formation").order_by(*ordre))
    evaluees = list(promo.inscriptions.filter(statut__in=[S.EN_COURS, S.VALIDEE, S.NON_VALIDEE])
                    .select_related("apprenant", "formation", "soutenance").order_by(*ordre))
    prerequis = list(formation.prerequis.all())
    criteres = list(formation.criteres.all())

    if request.method == "POST":
        if not peut_saisir:
            raise PermissionDenied
        if request.POST.get("quoi") == "prerequis":
            for insc in a_preparer:
                grille.definir_prerequis(insc, {p.pk: request.POST.get(f"p_{insc.pk}_{p.pk}") for p in prerequis})
            messages.success(request, "Prérequis enregistrés.")
        else:
            saisies, erreurs = {}, []
            for insc in (i for i in evaluees if i.statut == S.EN_COURS):  # résultats figés après la clôture
                nom = insc.apprenant.get_full_name() or insc.apprenant.username
                try:
                    saisies[insc] = ({c.pk: _note(request.POST.get(f"n_{insc.pk}_{c.pk}")) for c in criteres},
                                     _note(request.POST.get(f"s_{insc.pk}")))
                except ValueError as e:
                    erreurs.append(f"{nom} : « {e} » n'est pas une note entre 0 et 20")
            if erreurs:
                messages.error(request, "Rien n'a été enregistré. " + " ; ".join(erreurs) + ".")
            else:
                with transaction.atomic():
                    for insc, (notes, soutenance) in saisies.items():
                        grille.enregistrer_notes(insc, notes)
                        if soutenance is None:
                            Soutenance.objects.filter(inscription=insc).update(note_sur_20=None)
                        else:
                            Soutenance.objects.update_or_create(inscription=insc, defaults={"note_sur_20": soutenance})
                messages.success(request, "Évaluation enregistrée.")
        return redirect(f"{request.path}#{request.POST.get('quoi', 'notes')}")

    etats = {}
    for e in PrerequisInscription.objects.filter(inscription__in=a_preparer).values_list("inscription_id", "prerequis_id", "statut"):
        etats[(e[0], e[1])] = e[2]
    lignes_prerequis = [{"inscription": i, "faits": sum(1 for p in prerequis if etats.get((i.pk, p.pk)) == grille.OK),
                         "cases": [{"prerequis": p, "statut": etats.get((i.pk, p.pk), grille.A_FAIRE)} for p in prerequis]}
                        for i in a_preparer]
    libelles = dict(PrerequisInscription.Statut.choices)
    for ligne in lignes_prerequis:
        for case in ligne["cases"]:
            case["libelle"] = libelles[case["statut"]]
    lignes_notes = []
    for i in evaluees:
        notes = grille.notes_criteres(i)
        s = synthese(i)
        soutenance = getattr(i, "soutenance", None)
        lignes_notes.append({
            "inscription": i, "modifiable": peut_saisir and i.statut == S.EN_COURS,
            "notes": [{"critere": c, "note": notes.get(c.pk)} for c in criteres],
            "soutenance": soutenance.note_sur_20 if soutenance else None,
            "continu": s["moyenne_seances"], "projet": grille.note_projet(i, criteres, notes),
            "finale": s["note_globale"], "manques": grille.evaluation_incomplete(i, criteres)})
    return render(request, "evaluation/evaluation_promotion.html", {
        "promotion": promo, "formation": formation, "peut_saisir": peut_saisir,
        "prerequis": prerequis, "criteres": criteres, "statuts_prerequis": PrerequisInscription.Statut.choices,
        "lignes_prerequis": lignes_prerequis, "lignes_notes": lignes_notes,
        "composantes": grille.composantes(formation, bool(criteres)),
    })


@login_required
def attestation_pdf(request, inscription_id):
    """PDF de l'attestation : l'apprenant concerné, l'administration et les formateurs de la promotion."""
    from django.http import HttpResponse
    from django.urls import reverse
    from . import attestation
    insc = get_object_or_404(Inscription.objects.select_related("apprenant", "formation", "promotion"), pk=inscription_id)
    autorise = insc.apprenant_id == request.user.pk or (
        role_de(request.user) != APPRENANT and promotions_visibles(request.user).filter(pk=insc.promotion_id).exists())
    if not autorise or not attestation.est_valide(insc):
        raise Http404
    url = request.build_absolute_uri(reverse("verifier_attestation", args=[insc.code_attestation]))
    reponse = HttpResponse(attestation.pdf(insc, url), content_type="application/pdf")
    reponse["Content-Disposition"] = f'inline; filename="attestation-{insc.code_attestation}.pdf"'
    return reponse


def verifier_attestation(request, code):
    """Page publique : authenticité d'une attestation à partir de son numéro (QR code du PDF)."""
    from . import attestation
    insc = (Inscription.objects.select_related("apprenant", "formation", "promotion")
            .filter(code_attestation=code.strip().upper()).first())
    debut, fin = attestation.periode(insc) if insc else (None, None)
    return render(request, "evaluation/verifier_attestation.html", {
        "code": code, "inscription": insc, "valide": bool(insc) and attestation.est_valide(insc),
        "debut": debut, "fin": fin}, status=200 if insc else 404)
