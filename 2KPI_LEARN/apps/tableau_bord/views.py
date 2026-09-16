from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from apps.evaluation.models import Inscription
from . import services

@login_required
def accueil(request):
    inscription = Inscription.objects.filter(apprenant=request.user).first()
    donnees = services.synthese(inscription) if inscription else None
    return render(request, "tableau_bord/accueil.html",
                  {"inscription": inscription, "synthese": donnees})
