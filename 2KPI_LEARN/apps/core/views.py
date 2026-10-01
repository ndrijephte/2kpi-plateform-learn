"""Espace Paramètres : tout le paramétrage de la plateforme, réservé à l'admin."""
from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.db.models.deletion import ProtectedError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from apps.agenda.models import Indisponibilite
from apps.formation.models import Competence, Formation, Module, Seance
from apps.evaluation.gift import importer_gift
from apps.evaluation.models import Question, Quiz
from .forms import (AIDE_TYPES, SECTIONS, ChoixFormSet, CompetenceForm, FormationForm, GiftForm,
                    IndisponibiliteForm, ModuleForm, QuestionForm, QuizForm, SeanceForm,
                    parametres_form, verifier_question)
from .models import Parametres
from .permissions import admin_requis


# ---------- Fil d'Ariane : (libellé, url) ; la dernière étape n'a pas d'url ----------

def _fil(*etapes):
    return [("Paramètres", reverse("core:parametres"))] + list(etapes)


def _fil_formation(f, lien=True):
    return [("Formations & séances", reverse("core:formations")),
            (f.titre, reverse("core:formation", args=[f.pk]) if lien else None)]


def _fil_module(m, lien=True):
    return _fil_formation(m.formation) + [
        (f"{m.code} — {m.titre}", reverse("core:module", args=[m.pk]) if lien else None)]


def _fil_quiz(q=None, lien=True):
    etapes = [("Quiz", reverse("core:quiz_liste"))]
    if q:
        etapes.append((q.titre, reverse("core:quiz", args=[q.pk]) if lien else None))
    return etapes


@admin_requis
def accueil(request):
    return redirect("core:section", section="identite")


@admin_requis
def section(request, section):
    if section not in SECTIONS:
        raise Http404
    titre, _ = SECTIONS[section]
    Form = parametres_form(section)
    form = Form(request.POST or None, request.FILES or None, instance=Parametres.charger())
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"« {titre} » enregistré.")
        return redirect("core:section", section=section)
    return render(request, "parametres/section.html",
                  {"form": form, "section": section, "titre": titre, "fil": _fil((titre, None))})


# ---------- Catalogue : formations, modules, séances, compétences ----------

@admin_requis
def formations(request):
    form = FormationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        f = form.save()
        messages.success(request, f"Formation « {f.titre} » créée.")
        return redirect("core:formation", pk=f.pk)
    liste = Formation.objects.annotate(nb_modules=Count("modules", distinct=True),
                                       nb_promos=Count("promotions", distinct=True)).order_by("titre")
    return render(request, "parametres/formations.html",
                  {"formations": liste, "form": form, "section": "formations",
                   "fil": _fil(("Formations & séances", None))})


@admin_requis
def formation(request, pk):
    f = get_object_or_404(Formation, pk=pk)
    form = FormationForm(request.POST if request.POST.get("quoi") == "formation" else None, instance=f)
    module_form = ModuleForm(request.POST if request.POST.get("quoi") == "module" else None,
                             instance=Module(formation=f, ordre=f.modules.count() + 1))
    if request.method == "POST":
        if form.is_bound and form.is_valid():
            form.save()
            messages.success(request, "Formation mise à jour.")
            return redirect("core:formation", pk=f.pk)
        if module_form.is_bound and module_form.is_valid():
            m = module_form.save()
            messages.success(request, f"Module {m.code} ajouté.")
            return redirect("core:module", pk=m.pk)
    modules = f.modules.annotate(nb_seances=Count("seances", distinct=True),
                                 nb_competences=Count("competences", distinct=True)).order_by("ordre")
    return render(request, "parametres/formation.html", {
        "formation": f, "form": form, "module_form": module_form, "modules": modules,
        "section": "formations", "fil": _fil(*_fil_formation(f, lien=False))})


@admin_requis
def module(request, pk):
    m = get_object_or_404(Module.objects.select_related("formation"), pk=pk)
    quoi = request.POST.get("quoi")
    form = ModuleForm(request.POST if quoi == "module" else None, instance=m)
    seance_form = SeanceForm(request.POST if quoi == "seance" else None,
                             instance=Seance(module=m, ordre=m.seances.count() + 1, semaine=m.ordre))
    comp_form = CompetenceForm(request.POST if quoi == "competence" else None,
                               instance=Competence(module=m))
    if request.method == "POST":
        for f, msg in ((form, "Module mis à jour."), (seance_form, "Séance ajoutée."),
                       (comp_form, "Compétence ajoutée.")):
            if f.is_bound and f.is_valid():
                f.save()
                messages.success(request, msg)
                return redirect("core:module", pk=m.pk)
    return render(request, "parametres/module.html", {
        "module": m, "form": form, "seance_form": seance_form, "comp_form": comp_form,
        "seances": m.seances.all(), "competences": m.competences.all(), "section": "formations",
        "ouvrir": quoi, "fil": _fil(*_fil_module(m, lien=False))})


EDITABLES = {
    "seance": (Seance, SeanceForm, "Séance"),
    "competence": (Competence, CompetenceForm, "Compétence"),
    "indisponibilite": (Indisponibilite, IndisponibiliteForm, "Jour non travaillé"),
}
SUPPRIMABLES = {"formation": Formation, "module": Module, "seance": Seance,
                "competence": Competence, "indisponibilite": Indisponibilite,
                "quiz": Quiz, "question": Question}


def _blocage(modele, obj):
    """Refuse une suppression qui effacerait en cascade des données d'apprenants."""
    from apps.evaluation.models import Livrable, Presence
    if modele == "quiz" and obj.tentatives.exists():
        return "Des apprenants ont déjà passé ce quiz : modifie ses questions plutôt que de le supprimer."
    if modele == "formation" and obj.promotions.exists():
        return "Cette formation a des promotions : désactive-la plutôt (case « Active »)."
    seances = None
    if modele == "module":
        seances = Seance.objects.filter(module=obj)
    elif modele == "seance":
        seances = Seance.objects.filter(pk=obj.pk)
    if seances is not None and (Livrable.objects.filter(seance__in=seances).exists()
                                or Presence.objects.filter(seance__in=seances).exists()):
        return "Des livrables ou présences y sont rattachés : modifie l'élément plutôt que de le supprimer."
    return None


def _retour(request, defaut):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, {request.get_host()}, request.is_secure()):
        return nxt
    return defaut


@admin_requis
def modifier(request, modele, pk):
    if modele not in EDITABLES:
        raise Http404
    Model, Form, libelle = EDITABLES[modele]
    obj = get_object_or_404(Model, pk=pk)
    form = Form(request.POST or None, instance=obj)
    retour = _retour(request, reverse("core:calendrier" if modele == "indisponibilite" else "core:formations"))
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{libelle} enregistrée.")
        return redirect(retour)
    if modele == "seance":
        fil = _fil(*_fil_module(obj.module), (f"Séance {obj.ordre} — {obj.theme or obj.get_jour_display()}", None))
    elif modele == "competence":
        fil = _fil(*_fil_module(obj.module), (f"Compétence {obj.code}", None))
    else:
        fil = _fil(("Jours non travaillés", reverse("core:calendrier")), (str(obj.motif or obj.date_debut), None))
    return render(request, "parametres/objet_form.html", {"fil": fil,
        "form": form, "titre_page": f"{libelle} — {obj}", "libelle": libelle, "retour": retour,
        "section": "calendrier" if modele == "indisponibilite" else "formations"})


@admin_requis
def supprimer(request, modele, pk):
    if modele not in SUPPRIMABLES or request.method != "POST":
        raise Http404
    obj = get_object_or_404(SUPPRIMABLES[modele], pk=pk)
    motif = _blocage(modele, obj)
    if motif:
        messages.error(request, f"Suppression refusée. {motif}")
        return redirect(_retour(request, "core:formations"))
    try:
        nom = str(obj)
        obj.delete()
        messages.success(request, f"« {nom} » supprimé.")
    except ProtectedError:
        messages.error(request, "Suppression impossible : élément encore utilisé.")
    return redirect(_retour(request, "core:formations"))


# ---------- Calendrier : jours non travaillés ----------

@admin_requis
def calendrier(request):
    form = IndisponibiliteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Jour non travaillé ajouté. Il sera évité à la prochaine génération de calendrier.")
        return redirect("core:calendrier")
    return render(request, "parametres/calendrier.html", {
        "form": form, "section": "calendrier", "fil": _fil(("Jours non travaillés", None)),
        "indisponibilites": Indisponibilite.objects.select_related("promotion").order_by("date_debut")})


# ---------- Quiz : quiz, questions, réponses, import GIFT ----------

@admin_requis
def quiz_liste(request):
    form = QuizForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        q = form.save()
        messages.success(request, f"Quiz « {q.titre} » créé. Ajoute ses questions ou importe un fichier GIFT.")
        return redirect("core:quiz", pk=q.pk)
    liste = (Quiz.objects.select_related("module__formation")
             .annotate(nb_questions=Count("questions", distinct=True),
                       nb_tentatives=Count("tentatives", distinct=True))
             .order_by("module__formation__titre", "module__ordre", "titre"))
    return render(request, "parametres/quiz_liste.html", {
        "quiz_liste": liste, "form": form, "section": "quiz", "fil": _fil(("Quiz", None))})


@admin_requis
def quiz(request, pk):
    q = get_object_or_404(Quiz.objects.select_related("module__formation"), pk=pk)
    quoi = request.POST.get("quoi")
    form = QuizForm(request.POST if quoi == "quiz" else None, instance=q)
    gift = GiftForm(request.POST if quoi == "gift" else None, request.FILES if quoi == "gift" else None)
    if request.method == "POST":
        if form.is_bound and form.is_valid():
            form.save()
            messages.success(request, "Quiz mis à jour.")
            return redirect("core:quiz", pk=q.pk)
        if gift.is_bound and gift.is_valid():
            n = importer_gift(q, gift.texte, remplacer=gift.cleaned_data["remplacer"])
            if n:
                messages.success(request, f"{n} question(s) importée(s).")
            else:
                messages.error(request, "Aucune question reconnue dans ce fichier GIFT.")
            return redirect("core:quiz", pk=q.pk)
    return render(request, "parametres/quiz.html", {
        "quiz": q, "form": form, "gift": gift, "section": "quiz", "ouvrir": quoi,
        "questions": q.questions.prefetch_related("choix").order_by("id"),
        "nb_tentatives": q.tentatives.count(), "fil": _fil(*_fil_quiz(q, lien=False))})


@admin_requis
def question(request, quiz_pk, pk=None):
    q = get_object_or_404(Quiz.objects.select_related("module"), pk=quiz_pk)
    obj = get_object_or_404(Question, pk=pk, quiz=q) if pk else Question(quiz=q)
    data = request.POST if request.method == "POST" else None
    form = QuestionForm(data, instance=obj)
    formset = ChoixFormSet(data, instance=obj, prefix="choix")
    erreurs = []
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        choix = [(f.cleaned_data["texte"].strip(), f.cleaned_data.get("correct", False))
                 for f in formset.forms
                 if f.cleaned_data.get("texte") and not f.cleaned_data.get("DELETE")]
        type_q = form.cleaned_data["type"]
        erreurs = verifier_question(type_q, form.cleaned_data.get("reponse_courte", ""), choix)
        if not erreurs:
            with transaction.atomic():
                question = form.save()
                if type_q in ("court", "num"):
                    question.choix.all().delete()  # ces types n'utilisent pas de réponses proposées
                else:
                    formset.instance = question
                    for c in formset.save(commit=False):
                        if not c.texte.strip():
                            continue
                        c.poids = 100 if c.correct or type_q == "appariement" else 0
                        c.correct = c.correct or type_q == "appariement"
                        c.save()
                    for c in formset.deleted_objects:
                        c.delete()
            messages.success(request, "Question enregistrée.")
            if request.POST.get("suite"):
                return redirect("core:question_ajouter", quiz_pk=q.pk)
            return redirect("core:quiz", pk=q.pk)
    rang = list(q.questions.order_by("id").values_list("pk", flat=True))
    libelle = f"Question {rang.index(obj.pk) + 1}" if obj.pk else "Nouvelle question"
    return render(request, "parametres/question.html", {
        "quiz": q, "question": obj, "form": form, "formset": formset, "erreurs": erreurs,
        "aide_types": AIDE_TYPES, "section": "quiz", "libelle": libelle,
        "aide_liste": [(Question.Type(k).label, v) for k, v in AIDE_TYPES.items()],
        "fil": _fil(*_fil_quiz(q), (libelle, None))})


# ---------- Fichiers publics de media/ (logo, image de connexion, photos de profil) ----------

DOSSIERS_PUBLICS = ("parametres/", "profils/")


def media_publique(request, chemin):
    """Sert les fichiers publics de MEDIA_ROOT, y compris en production (Passenger ne les sert pas).
    Liste blanche de dossiers ; `serve` protège contre la remontée de chemin (../)."""
    from django.conf import settings
    from django.views.static import serve
    if not chemin.startswith(DOSSIERS_PUBLICS):
        raise Http404
    reponse = serve(request, chemin, document_root=settings.MEDIA_ROOT)
    reponse["Cache-Control"] = "public, max-age=86400"
    reponse["X-Content-Type-Options"] = "nosniff"
    return reponse
