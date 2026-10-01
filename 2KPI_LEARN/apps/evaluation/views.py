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
from apps.core.permissions import ADMIN, APPRENANT, formateur_requis, promotions_visibles, role_de, role_requis
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
    inscriptions = (Inscription.objects
                    .filter(promotion__in=promotions_visibles(request.user),
                            formation_id=quiz.module.formation_id)
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
    qs = (Livrable.objects.filter(rendu=True, inscription__promotion__in=promos)
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
    """Fichier d'un livrable : son auteur, le formateur de sa promotion ou un admin."""
    l = get_object_or_404(Livrable.objects.select_related("inscription"), pk=pk)
    autorise = (l.inscription.apprenant_id == request.user.pk
                or role_de(request.user) == ADMIN
                or promotions_visibles(request.user).filter(pk=l.inscription.promotion_id).exists())
    if not autorise:
        raise PermissionDenied
    if not l.fichier:
        raise Http404
    try:
        return FileResponse(l.fichier.open("rb"), as_attachment=True, filename=l.fichier.name.rsplit("/", 1)[-1])
    except FileNotFoundError:
        raise Http404
