from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Max, Q
from django.http import FileResponse, Http404
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from apps.core.fichiers import valider_fichier
from apps.core.permissions import APPRENANT, formateur_requis, formations_gerables, modules_gerables, role_de
from .acces import acces_module, etats_formateur, etats_modules
from .forms import CibleForm, DocumentsFormSet, ObjectifsForm, RessourceForm
from .models import Formation, Module, Ressource, Seance
from apps.agenda.models import Evenement
from apps.evaluation.models import Livrable
from apps.evaluation import autoevaluation
from apps.evaluation.models import AutoEvaluation
from apps.evaluation.utils import inscription_courante, meilleurs_scores


def _formations_accessibles(request):
    """Formations qu'on peut parcourir : celle de l'inscription (apprenant), celles où l'admin a
    attribué des modules (formateur), toutes (admin). Jamais une formation « par défaut »."""
    if role_de(request.user) == APPRENANT:
        insc = inscription_courante(request.user)
        return Formation.objects.filter(pk=insc.formation_id) if insc else Formation.objects.none()
    return formations_gerables(request.user)


def _formation_choisie(request):
    """Formation affichée : ?formation=<id> parmi les formations accessibles, sinon la première."""
    formations = _formations_accessibles(request).order_by("-active", "titre")
    f_id = request.GET.get("formation", "")
    return (formations.filter(pk=f_id).first() if f_id.isdigit() else None) or formations.first(), formations


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
    formation, formations = _formation_choisie(request)
    modules = []
    if formation:
        rendus = _livrables_rendus(insc)
        scores = meilleurs_scores(insc)
        qs = list(formation.modules.annotate(nb_competences=Count("competences", distinct=True))
                  .prefetch_related("seances", "quiz").order_by("ordre"))
        apprenant = role_de(request.user) == APPRENANT
        etats = etats_modules(insc, qs) if apprenant else etats_formateur(request.user, qs)
        for m in qs:
            ids = [s.id for s in m.seances.all()]
            faits = sum(1 for i in ids if i in rendus)
            quiz = next(iter(m.quiz.all()), None)
            modules.append({
                "module": m, "nb_seances": len(ids), "faits": faits,
                "pct": round(100 * faits / len(ids)) if ids else 0,
                "nb_competences": m.nb_competences,
                "quiz": quiz, "score": scores.get(quiz.id) if quiz else None,
                "acces": etats.get(m.id),
            })
    return render(request, "formation/modules.html",
                  {"formation": formation, "modules": modules, "inscription": insc,
                   "formations": formations if formations.count() > 1 else None})


@login_required
def detail_module(request, code):
    insc = inscription_courante(request.user)
    modules = Module.objects.filter(code=code, formation__in=_formations_accessibles(request))
    f_id = request.GET.get("formation", "")
    if f_id.isdigit():
        modules = modules.filter(formation_id=f_id)
    module = modules.order_by("formation_id").first()
    if module is None:
        raise Http404
    etat = acces_module(request.user, module)
    if not etat.ouvert:
        return _verrouille(request, module, etat)
    rendus = _livrables_rendus(insc)
    dates = _dates_promo(insc)
    liste = list(module.seances.prefetch_related("objectifs_seance"))
    objectifs = {s.id: [o for o in s.objectifs_seance.all() if o.actif] for s in liste}
    evals = autoevaluation.evaluations_de(insc, [o for objs in objectifs.values() for o in objs])
    seances = [{"seance": s, "rendu": s.id in rendus, "evenement": dates.get(s.id),
                "autoeval": autoevaluation.bilan_seance(evals, objectifs[s.id])}
               for s in liste]
    quiz = module.quiz.first()
    score = meilleurs_scores(insc).get(quiz.id) if quiz else None
    return render(request, "formation/module_detail.html", {
        "module": module, "seances": seances, "quiz": quiz, "score": score,
        "competences": module.competences.all(), "ressources": module.ressources.all(),
        "peut_gerer": role_de(request.user) != APPRENANT,  # module ouvert ⇒ attribué au formateur
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
    objectifs = list(seance.objectifs_seance.filter(actif=True))
    peut_s_evaluer = bool(insc) and role_de(request.user) == APPRENANT

    gere_objectifs = (role_de(request.user) != APPRENANT
                      and modules_gerables(request.user).filter(pk=seance.module_id).exists())
    objectifs_form = ObjectifsForm(request.POST if request.POST.get("action") == "objectifs" else None,
                                   seance=seance) if gere_objectifs else None
    if request.method == "POST" and request.POST.get("action") == "objectifs":
        if not gere_objectifs:
            raise PermissionDenied
        if objectifs_form.is_valid():
            _enregistrer_objectifs(request, seance, objectifs_form)
            return redirect(f"{reverse('formation:seance', args=[seance.pk])}#objectifs")

    if request.method == "POST" and request.POST.get("action") == "autoevaluation":
        if not peut_s_evaluer:
            messages.error(request, "L'auto-évaluation est réservée aux apprenants inscrits à la formation.")
            return redirect("formation:seance", pk=seance.pk)
        n, aides = autoevaluation.enregistrer(insc, objectifs, request.POST)
        autoevaluation.signaler_besoin_aide(insc, seance, aides)
        if not n:
            messages.error(request, "Choisis ton niveau pour au moins un objectif.")
        else:
            messages.success(request, "Auto-évaluation enregistrée." + (
                " Ton formateur est prévenu de ta demande d'aide." if aides else ""))
        return redirect(f"{reverse('formation:seance', args=[seance.pk])}#autoevaluation")

    if request.method == "POST" and request.POST.get("action") != "objectifs":  # dépôt du livrable
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

    ressources = list(seance.ressources.select_related("ajoute_par"))
    evals = autoevaluation.evaluations_de(insc, objectifs) if peut_s_evaluer else {}
    return render(request, "formation/seance_detail.html", {
        "objectifs": [{"objectif": o, "eval": evals.get(o.pk)} for o in objectifs],
        "bilan_autoeval": autoevaluation.bilan_seance(evals, objectifs),
        "peut_s_evaluer": peut_s_evaluer, "niveaux": autoevaluation.echelle(),
        "promotions_seance": _promotions_du_module(request.user, seance.module) if role_de(request.user) != APPRENANT else [],
        "seance": seance, "livrable": livrable, "inscription": insc,
        "ressources": ressources, "visios": [r for r in ressources if r.est_visio],
        "evenement": _dates_promo(insc).get(seance.id),
        "precedente": precedente, "suivante": suivante,
        "peut_gerer": role_de(request.user) != APPRENANT,
        "objectifs_form": objectifs_form, "editer_objectifs": bool(objectifs_form and objectifs_form.errors),
        "position": i + 1, "total": len(toutes),
    })


def _enregistrer_objectifs(request, seance, form):
    """Enregistre les objectifs et prévient les apprenants concernés des nouveaux."""
    nouveaux = form.enregistrer_objectifs(seance)
    n = autoevaluation.annoncer_objectifs(seance, nouveaux, par=request.user)
    total = seance.objectifs_seance.filter(actif=True).count()
    msg = f"{total} objectif{'s' if total > 1 else ''} enregistré{'s' if total > 1 else ''}."
    if nouveaux:
        msg += (f" {n} apprenant{'s' if n > 1 else ''} prévenu{'s' if n > 1 else ''}." if n else
                " Aucun apprenant n'a encore accès à ce module : ils les verront à son ouverture.")
    messages.success(request, msg)


def _promotions_du_module(user, module):
    """Promotions (actives) où l'utilisateur intervient sur ce module : liens vers la synthèse des auto-évaluations."""
    from apps.core.permissions import interventions, promotions_visibles
    perimetre = interventions(user)
    promos = promotions_visibles(user).filter(formation_id=module.formation_id, active=True)
    if perimetre is not None:
        promos = [p for p in promos if perimetre.get(p.pk) is None or module.pk in perimetre[p.pk]]
    return list(promos)


@formateur_requis
def objectifs_seance(request, pk):
    """Le formateur (ou l'admin) rédige les objectifs d'une séance de ses modules."""
    seance = get_object_or_404(Seance.objects.select_related("module", "module__formation"), pk=pk)
    if not modules_gerables(request.user).filter(pk=seance.module_id).exists():
        raise Http404
    form = ObjectifsForm(request.POST or None, seance=seance)
    if request.method == "POST" and form.is_valid():
        _enregistrer_objectifs(request, seance, form)
        return redirect(f"{reverse('formation:seance', args=[seance.pk])}#objectifs")
    archives = seance.objectifs_seance.filter(actif=False)
    return render(request, "formation/objectifs_form.html", {"seance": seance, "form": form, "archives": archives})


# ---------- Ressources pédagogiques (formateur / admin) ----------

def _module_de_ressource(r):
    return r.seance.module_id if r.seance_id else r.module_id


def _retour_sur(request, defaut):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, {request.get_host()}, request.is_secure()):
        return nxt
    return defaut


@formateur_requis
def ressources(request):
    """Bibliothèque des ressources des modules attribués, groupées par module."""
    formations = formations_gerables(request.user)
    modules = modules_gerables(request.user)
    qs = (Ressource.objects.filter(Q(seance__module__in=modules) | Q(module__in=modules))
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
def ressource_editer(request, pk):
    modules = modules_gerables(request.user)
    r = get_object_or_404(Ressource.objects.select_related("seance__module", "module"), pk=pk)
    if not modules.filter(pk=_module_de_ressource(r)).exists():
        raise Http404
    ancien = r.fichier.name if r.fichier else None
    form = RessourceForm(request.POST or None, request.FILES or None, instance=r, modules=modules)
    retour = _retour_sur(request, reverse("formation:ressources"))
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        if ancien and ancien != (obj.fichier.name if obj.fichier else None):
            obj.fichier.storage.delete(ancien)  # fichier remplacé ou retiré
        messages.success(request, f"Ressource « {obj.titre} » mise à jour.")
        return redirect(retour)
    return render(request, "formation/ressource_form.html", {
        "form": form, "ressource": r, "retour": retour})


@formateur_requis
def documents_ajouter(request):
    """Ajout groupé : plusieurs documents (fichiers, notebooks, lien de classe virtuelle…) décrits un à un."""
    initial = {k: request.GET[k] for k in ("seance", "module") if request.GET.get(k, "").isdigit()}
    cible = CibleForm(request.POST or None, modules=modules_gerables(request.user), initial=initial)
    docs = DocumentsFormSet(request.POST or None, request.FILES or None,
                            queryset=Ressource.objects.none(), prefix="docs")
    retour = _retour_sur(request, reverse("formation:ressources"))
    if request.method == "POST":
        cible_ok, docs_ok = cible.is_valid(), docs.is_valid()  # valider les deux pour afficher toutes les erreurs
        remplis = [f for f in docs.forms if f.has_changed()] if docs_ok else []
        if docs_ok and not remplis:
            messages.error(request, "Ajoute au moins un document (fichier ou lien).")
        elif cible_ok and docs_ok:
            seance, module = cible.cleaned_data["seance"], cible.cleaned_data["module"]
            voisines = Ressource.objects.filter(seance=seance) if seance else Ressource.objects.filter(module=module)
            ordre = (voisines.aggregate(m=Max("ordre"))["m"] or 0) + 1 if voisines.exists() else 0
            with transaction.atomic():
                for i, f in enumerate(remplis):
                    r = f.save(commit=False)
                    r.seance, r.module, r.ordre, r.ajoute_par = seance, module, ordre + i, request.user
                    r.save()
            n = len(remplis)
            messages.success(request, f"{n} document{'s' if n > 1 else ''} ajouté{'s' if n > 1 else ''} "
                                      f"à {seance.theme or seance if seance else module}.")
            return redirect(retour)
    return render(request, "formation/documents_form.html", {"cible": cible, "docs": docs, "retour": retour})


@formateur_requis
def ressource_supprimer(request, pk):
    r = get_object_or_404(Ressource.objects.select_related("seance__module", "module"), pk=pk)
    if request.method != "POST" or not modules_gerables(request.user).filter(
            pk=_module_de_ressource(r)).exists():
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
