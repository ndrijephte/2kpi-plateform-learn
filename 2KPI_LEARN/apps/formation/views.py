from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from .models import Formation, Module, Seance
from apps.evaluation.models import Livrable
from apps.evaluation.utils import inscription_courante


@login_required
def liste_modules(request):
    formation = Formation.objects.filter(active=True).first()
    modules = formation.modules.all() if formation else []
    return render(request, "formation/modules.html",
                  {"formation": formation, "modules": modules})


@login_required
def detail_module(request, code):
    module = get_object_or_404(Module, code=code)
    quiz = module.quiz.first()
    return render(request, "formation/module_detail.html",
                  {"module": module, "quiz": quiz})


@login_required
def detail_seance(request, pk):
    seance = get_object_or_404(Seance, pk=pk)
    insc = inscription_courante(request.user)
    livrable = None
    if insc:
        livrable = Livrable.objects.filter(inscription=insc, seance=seance).first()

    if request.method == "POST" and insc:
        fichier = request.FILES.get("fichier")
        livrable, _ = Livrable.objects.get_or_create(inscription=insc, seance=seance)
        if fichier:
            livrable.fichier = fichier
        livrable.rendu = True
        livrable.save()
        messages.success(request, "Livrable déposé. Ton formateur pourra le noter.")
        return redirect("formation:seance", pk=seance.pk)

    return render(request, "formation/seance_detail.html",
                  {"seance": seance, "livrable": livrable,
                   "ressources": seance.ressources.all()})
