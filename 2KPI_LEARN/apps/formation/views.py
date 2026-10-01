from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from apps.core.fichiers import valider_fichier
from apps.core.permissions import APPRENANT, formateur_requis, formations_gerables, role_de
from .acces import acces_module, etats_modules
from .forms import RessourceForm
from .models import Formation, Module, Ressource, Seance
from apps.agenda.models import Evenement
from apps.evaluation.models import Livrable
from apps.evaluation.utils import inscription_courante, meilleurs_scores


def _formation_de(insc):
    """Formation suivie par l'apprenant, sinon la première formation active."""
    if insc:
        return insc.formation
    return Formation.objects.filter(active=True).first()


def _verrouille(request, module, etat):
    """Page « contenu verrouillé » (403) avec l'explication de l'autorisation manquante."""
    return render(request, "formation/verrouille.html", {"module": module, "etat": etat}, status=403)


def _livrables_rendus(insc):
    if not insc:
        return set()
    return set(Livrable.objects.filter(inscription=insc, rendu=True).values_list("seance_id", flat=True))


def _dates_promo(insc):
    """{seance_id: Evenement} pour la promotion de l'apprenant."""
    if not insc or not insc.promotion_id:
        return {}
    evs = Evenement.objects.filter(promotion_id=insc.promotion_id, seance__isnull=False)
    return {e.seance_id: e for e in evs}


@login_required
def liste_modules(request):
    insc = inscription_courante(request.user)
    formation = _formation_de(insc)
    modules = []
    if formation:
        rendus = _livrables_rendus(insc)
        scores = meilleurs_scores(insc)
        qs = list(formation.modules.annotate(nb_competences=Count("competences", distinct=True))
                  .prefetch_related("seances", "quiz").order_by("ordre"))
        apprenant = role_de(request.user) == APPRENANT
        etats = etats_modules(insc, qs) if apprenant else {}
        for m in qs:
            ids = [s.id for s in m.seances.all()]
            faits = sum(1 for i in ids if i in rendus)
            quiz = next(iter(m.quiz.all()), None)
            modules.append({
                "module": m, "nb_seances": len(ids), "faits": faits,
                "pct": round(100 * faits / len(ids)) if ids else 0,
                "nb_competences": m.nb_competences,
                "quiz": quiz, "score": scores.get(quiz.id) if quiz else None,
                "acces": etats.get(m.id) if apprenant else None,
            })
    return render(request, "formation/modules.html",
                  {"formation": formation, "modules": modules, "inscription": insc})


@login_required
def detail_module(request, code):
    insc = inscription_courante(request.user)
    formation = _formation_de(insc)
    module = get_object_or_404(Module, formation=formation, code=code)
    etat = acces_module(request.user, module)
    if not etat.ouvert:
        return _verrouille(request, module, etat)
    rendus = _livrables_rendus(insc)
    dates = _dates_promo(insc)
    seances = [{"seance": s, "rendu": s.id in rendus, "evenement": dates.get(s.id)}
               for s in module.seances.all()]
    quiz = module.quiz.first()
    score = meilleurs_scores(insc).get(quiz.id) if quiz else None
    return render(request, "formation/module_detail.html", {
        "module": module, "seances": seances, "quiz": quiz, "score": score,
        "competences": module.competences.all(), "ressources": module.ressources.all(),
        "peut_gerer": formations_gerables(request.user).filter(pk=module.formation_id).exists(),
    })


@login_required
def detail_seance(request, pk):
    seance = get_object_or_404(Seance.objects.select_related("module", "module__formation"), pk=pk)
    etat = acces_module(request.user, seance.module)
    if not etat.ouvert:
        return _verrouille(request, seance.module, etat)
    insc = inscription_courante(request.user)
    if insc and insc.formation_id != seance.module.formation_id:
        insc = None
    livrable = Livrable.objects.filter(inscription=insc, seance=seance).first() if insc else None

    if request.method == "POST":
        if not insc:
            messages.error(request, "Tu dois être inscrit à la formation pour déposer un livrable.")
            return redirect("formation:seance", pk=seance.pk)
        fichier = request.FILES.get("fichier")
        if not fichier and not (livrable and livrable.fichier):
            messages.error(request, "Choisis un fichier avant de valider le dépôt.")
            return redirect("formation:seance", pk=seance.pk)
        if fichier:
            try:
                valider_fichier(fichier)
            except ValidationError as e:
                messages.error(request, " ".join(e.messages))
                return redirect("formation:seance", pk=seance.pk)
        livrable, _ = Livrable.objects.get_or_create(inscription=insc, seance=seance)
        if fichier:
            livrable.fichier = fichier
        livrable.rendu = True
        livrable.save()
        messages.success(request, "Livrable déposé. Ton formateur pourra le noter.")
        return redirect("formation:seance", pk=seance.pk)

    # Navigation séance précédente / suivante dans toute la formation
    toutes = list(Seance.objects.filter(module__formation=seance.module.formation)
                  .values_list("pk", flat=True))
    i = toutes.index(seance.pk)
    precedente = toutes[i - 1] if i > 0 else None
    suivante = toutes[i + 1] if i + 1 < len(toutes) else None

    return render(request, "formation/seance_detail.html", {
        "seance": seance, "livrable": livrable, "inscription": insc,
        "ressources": seance.ressources.all(),
        "evenement": _dates_promo(insc).get(seance.id),
        "precedente": precedente, "suivante": suivante,
        "peut_gerer": formations_gerables(request.user).filter(pk=seance.module.formation_id).exists(),
        "position": i + 1, "total": len(toutes),
    })


# ---------- Ressources pédagogiques (formateur / admin) ----------

def _formation_de_ressource(r):
    return (r.seance.module.formation_id if r.seance_id else r.module.formation_id)


def _retour_sur(request, defaut):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, {request.get_host()}, request.is_secure()):
        return nxt
    return defaut


@formateur_requis
def ressources(request):
    """Bibliothèque des ressources des formations gérées, groupées par module."""
    formations = formations_gerables(request.user)
    qs = (Ressource.objects.filter(Q(seance__module__formation__in=formations) | Q(module__formation__in=formations))
          .select_related("seance__module", "module", "ajoute_par"))
    f_id = request.GET.get("formation", "")
    if f_id.isdigit():
        qs = qs.filter(Q(seance__module__formation_id=f_id) | Q(module__formation_id=f_id))
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(titre__icontains=q) | Q(instructions__icontains=q))
    groupes = {}
    for r in qs:
        m = r.seance.module if r.seance_id else r.module
        groupes.setdefault(m, []).append(r)
    groupes = sorted(groupes.items(), key=lambda kv: (kv[0].formation_id, kv[0].ordre))
    return render(request, "formation/ressources.html", {
        "groupes": groupes, "total": qs.count(), "formations": formations, "f_id": f_id, "q": q})


@formateur_requis
def ressource_editer(request, pk=None):
    formations = formations_gerables(request.user)
    r = None
    if pk:
        r = get_object_or_404(Ressource.objects.select_related("seance__module", "module"), pk=pk)
        if not formations.filter(pk=_formation_de_ressource(r)).exists():
            raise Http404
    initial = {}
    if not r:
        if request.GET.get("seance", "").isdigit():
            initial["seance"] = request.GET["seance"]
        if request.GET.get("module", "").isdigit():
            initial["module"] = request.GET["module"]
    ancien = r.fichier.name if r and r.fichier else None
    form = RessourceForm(request.POST or None, request.FILES or None, instance=r,
                         formations=formations, initial=initial)
    retour = _retour_sur(request, reverse("formation:ressources"))
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if not obj.pk:
            obj.ajoute_par = request.user
        obj.save()
        if ancien and ancien != (obj.fichier.name if obj.fichier else None):
            obj.fichier.storage.delete(ancien)  # fichier remplacé ou retiré
        messages.success(request, f"Ressource « {obj.titre} » {'mise à jour' if pk else 'ajoutée'}.")
        return redirect(retour)
    return render(request, "formation/ressource_form.html", {
        "form": form, "ressource": r, "retour": retour})


@formateur_requis
def ressource_supprimer(request, pk):
    r = get_object_or_404(Ressource.objects.select_related("seance__module", "module"), pk=pk)
    if request.method != "POST" or not formations_gerables(request.user).filter(
            pk=_formation_de_ressource(r)).exists():
        raise Http404
    if r.fichier:
        r.fichier.storage.delete(r.fichier.name)
    titre = r.titre
    r.delete()
    messages.success(request, f"Ressource « {titre} » supprimée.")
    return redirect(_retour_sur(request, reverse("formation:ressources")))


@login_required
def ressource_fichier(request, pk):
    """Téléchargement contrôlé d'une ressource (apprenant : module ouvert uniquement)."""
    r = get_object_or_404(Ressource.objects.select_related("seance__module", "module"), pk=pk)
    if not r.fichier:
        raise Http404
    module = r.seance.module if r.seance_id else r.module
    etat = acces_module(request.user, module)
    if not etat.ouvert:
        return _verrouille(request, module, etat)
    try:
        return FileResponse(r.fichier.open("rb"), as_attachment=True, filename=r.nom_fichier)
    except FileNotFoundError:
        raise Http404
