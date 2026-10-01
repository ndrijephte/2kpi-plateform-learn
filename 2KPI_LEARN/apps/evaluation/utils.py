from django.db.models import Max
from .models import Inscription, TentativeQuiz


def inscription_courante(user):
    """Inscription la plus récente de l'utilisateur (ou None)."""
    if not user.is_authenticated:
        return None
    return (Inscription.objects.filter(apprenant=user)
            .select_related("formation", "promotion").order_by("-id").first())


def meilleurs_scores(inscription):
    """{quiz_id: meilleur score /20} pour une inscription."""
    if not inscription:
        return {}
    return dict(TentativeQuiz.objects.filter(inscription=inscription)
                .values("quiz").annotate(best=Max("score")).values_list("quiz", "best"))
