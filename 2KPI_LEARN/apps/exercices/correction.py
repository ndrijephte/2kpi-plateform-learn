"""Notation des exercices et règles de visibilité des résultats.

- QCM, Vrai/Faux : tout ou rien (exactement les bonnes cases) ;
- réponse courte : comparée aux variantes acceptées, sans tenir compte de la casse, des accents
  ni des espaces superflus ;
- valeur numérique : juste si |réponse − attendue| ≤ tolérance (virgule acceptée) ;
- réponse rédigée : notée par le formateur après la date limite (vide = 0 d'office).
Le résultat n'est montré à l'apprenant qu'après la date limite et une fois toutes les réponses notées.
"""
import unicodedata
from decimal import Decimal, InvalidOperation
from django.db import transaction
from .models import Copie, Question, Reponse

T = Question.Type


def _normaliser(texte):
    texte = unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode()
    return " ".join(texte.lower().split())


def _nombre(texte):
    try:
        return Decimal((texte or "").strip().replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        return None


def choix_coches(valeur):
    return {int(x) for x in (valeur or "").split(",") if x.strip().isdigit()}


def points_automatiques(question, valeur):
    """Points obtenus pour une réponse ; None si la question se corrige à la main."""
    vide = not (valeur or "").strip()
    if question.type == T.REDACTION:
        return Decimal(0) if vide else None
    if vide:
        return Decimal(0)
    if question.type in (T.QCM, T.VF):
        justes = {c.pk for c in question.choix.all() if c.correct}
        ok = bool(justes) and choix_coches(valeur) == justes
    elif question.type == T.COURTE:
        acceptees = {_normaliser(a) for a in question.reponses_acceptees.split("|") if a.strip()}
        ok = _normaliser(valeur) in acceptees
    else:  # NUMERIQUE
        n = _nombre(valeur)
        ok = n is not None and question.valeur_attendue is not None and \
            abs(n - question.valeur_attendue) <= question.tolerance
    return question.points if ok else Decimal(0)


@transaction.atomic
def enregistrer_copie(planification, inscription, valeurs):
    """valeurs : {question_id: texte}. Crée ou met à jour la copie et note ce qui peut l'être."""
    copie, _ = Copie.objects.get_or_create(planification=planification, inscription=inscription)
    for question in planification.exercice.questions.prefetch_related("choix"):
        valeur = (valeurs.get(question.pk) or "").strip()
        Reponse.objects.update_or_create(copie=copie, question=question, defaults={
            "valeur": valeur, "points": points_automatiques(question, valeur), "commentaire": ""})
    copie.save(update_fields=["enregistree_le"])
    return copie


def resultat(planification, copie):
    """{"points", "bareme", "note_sur_20", "complet", "a_corriger"} d'une copie (None = rien rendu)."""
    questions = list(planification.exercice.questions.all())
    bareme = sum((q.points for q in questions), Decimal(0))
    reponses = {r.question_id: r for r in copie.reponses.all()} if copie else {}
    a_corriger = sum(1 for q in questions if q.pk in reponses and reponses[q.pk].points is None)
    points = sum((reponses[q.pk].points for q in questions if q.pk in reponses and reponses[q.pk].points is not None),
                 Decimal(0))
    note = (points * 20 / bareme).quantize(Decimal("0.01")) if bareme else Decimal(0)
    return {"points": points, "bareme": bareme, "note_sur_20": note, "complet": a_corriger == 0,
            "a_corriger": a_corriger}


def resultat_visible(planification, copie):
    """L'apprenant voit sa note et la correction : date limite passée et correction terminée."""
    return planification.termine and resultat(planification, copie)["complet"]
