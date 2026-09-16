from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from .models import Formation, Module

@login_required
def liste_modules(request):
    formation = Formation.objects.filter(active=True).first()
    modules = formation.modules.all() if formation else []
    return render(request, "formation/modules.html",
                  {"formation": formation, "modules": modules})

@login_required
def detail_module(request, code):
    module = get_object_or_404(Module, code=code)
    return render(request, "formation/module_detail.html", {"module": module})
