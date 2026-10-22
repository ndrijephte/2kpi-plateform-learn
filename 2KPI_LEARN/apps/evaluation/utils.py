from django.db.models import Max
from .models import Inscription, TentativeQuiz


def inscription_courante(user):
    """Inscription de référence de l'utilisateur (ou None) : la plus récente parmi celles « en cours »
    et rattachées à une promotion ; à défaut, la plus récente. Une candidature acceptée ou une
    inscription terminée plus récente ne masque donc pas la formation que l'apprenant suit."""
    if not user.is_authenticated:
        return None
    from django.db.models import Case, IntegerField, Q, Value, When
    return (Inscription.objects.filter(apprenant=user)
            .annotate(active=Case(When(Q(statut=Inscription.Statut.EN_COURS, promotion__isnull=False), then=Value(1)),
                                  default=Value(0), output_field=IntegerField()))
            .select_related("formation", "promotion").order_by("-active", "-id").first())


def meilleurs_scores(inscription):
    """{quiz_id: meilleur score /20} pour une inscription."""
    if not inscription:
        return {}
    return dict(TentativeQuiz.objects.filter(inscription=inscription)
                .values("quiz").annotate(best=Max("score")).values_list("quiz", "best"))
