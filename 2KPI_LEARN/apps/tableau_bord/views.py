from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from apps.evaluation.models import Inscription
from apps.agenda.models import Evenement
from . import services

@login_required
def accueil(request):
    inscription = Inscription.objects.filter(apprenant=request.user).first()
    donnees = services.synthese(inscription) if inscription else None
    prochaine = None
    if inscription and inscription.promotion_id:
        prochaine = (inscription.promotion.evenements
                     .filter(date_debut__gte=timezone.now())
                     .exclude(statut=Evenement.Statut.ANNULE)
                     .select_related("seance").first())
    return render(request, "tableau_bord/accueil.html",
                  {"inscription": inscription, "synthese": donnees, "prochaine": prochaine})
