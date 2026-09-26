import random
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from .models import Quiz, TentativeQuiz
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


@login_required
def quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    if request.method == "POST":
        score, bonnes, total, details = corriger(quiz, request.POST)
        insc = inscription_courante(request.user)
        if insc:
            TentativeQuiz.objects.create(inscription=insc, quiz=quiz, score=score)
        resultats = [{"q": q, "ok": ok} for q, ok in details]
        return render(request, "evaluation/quiz_result.html", {
            "quiz": quiz, "score": score, "bonnes": bonnes,
            "total": total, "resultats": resultats,
        })
    return render(request, "evaluation/quiz.html",
                  {"quiz": quiz, "questions": _prepare_questions(quiz)})
