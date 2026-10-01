from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from apps.agenda.models import Promotion
from apps.core.permissions import ADMIN, admin_requis, appliquer_role, role_de
from apps.evaluation.models import Inscription
from apps.evaluation.utils import inscription_courante
from .forms import CompteAdminForm, CompteForm, NouvelUtilisateurForm, PrerequisForm, ProfilForm
from .models import Profil, Prerequis

User = get_user_model()


@login_required
def profil(request):
    # Les comptes créés avant le signal (ex. createsuperuser initial) n'ont pas toujours de profil.
    profil, prerequis = _profil_complet(request.user)
    items = [(f.verbose_name, getattr(prerequis, f.name), getattr(prerequis, f"get_{f.name}_display")())
             for f in Prerequis._meta.fields if f.choices]
    faits = sum(1 for _, v, _ in items if v == Prerequis.Statut.OK)
    return render(request, "comptes/profil.html", {
        "profil": profil, "prerequis": items, "prerequis_ok": faits,
        "inscription": inscription_courante(request.user),
    })


def _profil_complet(user):
    profil, _ = Profil.objects.get_or_create(utilisateur=user)
    prerequis, _ = Prerequis.objects.get_or_create(profil=profil)
    return profil, prerequis


@login_required
def profil_modifier(request):
    """Chaque utilisateur (admin compris) modifie ses propres informations."""
    user = request.user
    profil, prerequis = _profil_complet(user)
    data, files = (request.POST, request.FILES) if request.method == "POST" else (None, None)
    compte_form = CompteForm(data, instance=user, prefix="c")
    profil_form = ProfilForm(data, files, instance=profil, prefix="p")
    prerequis_form = PrerequisForm(data, instance=prerequis, prefix="r") if role_de(user) == "apprenant" else None
    forms_ = [f for f in (compte_form, profil_form, prerequis_form) if f]
    if request.method == "POST" and all(f.is_valid() for f in forms_):
        for f in forms_:
            f.save()
        messages.success(request, "Profil mis à jour.")
        return redirect("comptes:profil")
    return render(request, "comptes/profil_form.html", {
        "compte_form": compte_form, "profil_form": profil_form, "prerequis_form": prerequis_form,
        "cible": user, "soi": True, "retour_url": reverse("comptes:profil"), "retour_label": "Mon profil"})


@admin_requis
def utilisateur_editer(request, pk):
    """L'admin modifie toutes les informations d'un compte (le sien compris)."""
    cible = get_object_or_404(User, pk=pk)
    profil, prerequis = _profil_complet(cible)
    insc = Inscription.objects.filter(apprenant=cible).order_by("-id").first()
    data, files = (request.POST, request.FILES) if request.method == "POST" else (None, None)
    compte_form = CompteAdminForm(data, instance=cible, prefix="c",
                                  initial={"role": role_de(cible), "promotion": insc.promotion_id if insc else None,
                                           "statut_inscription": insc.statut if insc else Inscription.Statut.EN_COURS})
    profil_form = ProfilForm(data, files, instance=profil, prefix="p")
    prerequis_form = PrerequisForm(data, instance=prerequis, prefix="r") if role_de(cible) == "apprenant" else None
    forms_ = [f for f in (compte_form, profil_form, prerequis_form) if f]
    if request.method == "POST" and all(f.is_valid() for f in forms_):
        role = compte_form.cleaned_data["role"]
        if cible == request.user and (role != ADMIN or not compte_form.cleaned_data["is_active"]):
            messages.error(request, "Tu ne peux ni retirer ton rôle d'administrateur ni désactiver ton propre compte.")
        else:
            with transaction.atomic():
                cible = compte_form.save()
                if compte_form.cleaned_data["nouveau_mdp"]:
                    cible.set_password(compte_form.cleaned_data["nouveau_mdp"])
                    cible.save(update_fields=["password"])
                profil_form.save()
                if prerequis_form:
                    prerequis_form.save()
                appliquer_role(cible, role)
                promo = compte_form.cleaned_data["promotion"]
                if role == Profil.Role.APPRENANT and promo:
                    insc = _rattacher(cible, promo)
                statut = compte_form.cleaned_data.get("statut_inscription")
                if insc and statut and insc.statut != statut:
                    insc.statut = statut
                    insc.save(update_fields=["statut"])
            if cible == request.user and compte_form.cleaned_data["nouveau_mdp"]:
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, cible)
            messages.success(request, f"Compte « {cible.username} » mis à jour.")
            return redirect("comptes:utilisateurs")
    return render(request, "comptes/profil_form.html", {
        "compte_form": compte_form, "profil_form": profil_form, "prerequis_form": prerequis_form,
        "cible": cible, "soi": cible == request.user,
        "retour_url": reverse("comptes:utilisateurs"), "retour_label": "Utilisateurs"})


def _rattacher(user, promotion):
    """Inscrit l'apprenant à la formation de la promotion et le rattache à celle-ci."""
    insc, _ = Inscription.objects.get_or_create(
        apprenant=user, formation=promotion.formation,
        defaults={"promotion": promotion, "date_debut": promotion.date_debut})
    if insc.promotion_id != promotion.id:
        insc.promotion = promotion
        insc.save(update_fields=["promotion"])
    return insc


@admin_requis
def utilisateurs(request):
    form = NouvelUtilisateurForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        with transaction.atomic():
            user = User.objects.create_user(d["username"], d["email"], d["password"],
                                            first_name=d["first_name"], last_name=d["last_name"])
            appliquer_role(user, d["role"])
            if d["role"] == Profil.Role.APPRENANT and d["promotion"]:
                _rattacher(user, d["promotion"])
        messages.success(request, f"Compte « {user.username} » créé ({user.profil.get_role_display()}).")
        return redirect("comptes:utilisateurs")

    filtre, q = request.GET.get("role", ""), request.GET.get("q", "").strip()
    qs = User.objects.select_related("profil").prefetch_related("inscriptions__promotion").order_by(
        "-is_active", "last_name", "first_name", "username")
    if filtre in Profil.Role.values:
        qs = qs.filter(profil__role=filtre)
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(first_name__icontains=q)
                       | Q(last_name__icontains=q) | Q(email__icontains=q))
    lignes = []
    for u in qs:
        insc = max(u.inscriptions.all(), key=lambda i: i.id, default=None)
        lignes.append({"u": u, "role": role_de(u), "promotion": insc.promotion if insc else None})
    compte = {r: Profil.objects.filter(role=r).count() for r in Profil.Role.values}
    return render(request, "comptes/utilisateurs.html", {
        "lignes": lignes, "form": form, "roles": Profil.Role.choices, "filtre": filtre, "q": q,
        "compte": compte, "promotions": Promotion.objects.filter(active=True).select_related("formation"),
        "ouvrir_formulaire": request.method == "POST",
    })


@admin_requis
def utilisateur_modifier(request, pk):
    user = get_object_or_404(User.objects.select_related("profil"), pk=pk)
    if request.method != "POST":
        return redirect("comptes:utilisateurs")
    action = request.POST.get("action")
    if action == "role":
        role = request.POST.get("role")
        if role not in Profil.Role.values:
            messages.error(request, "Rôle inconnu.")
        elif user == request.user and role != ADMIN:
            messages.error(request, "Tu ne peux pas retirer ton propre rôle d'administrateur.")
        else:
            appliquer_role(user, role)
            messages.success(request, f"{user.get_full_name() or user.username} est maintenant "
                                      f"« {user.profil.get_role_display()} ».")
    elif action == "promotion":
        promo = Promotion.objects.filter(pk=request.POST.get("promotion") or None).first()
        if promo:
            _rattacher(user, promo)
            messages.success(request, f"{user.username} rattaché à « {promo.nom} ».")
        else:
            Inscription.objects.filter(apprenant=user).update(promotion=None)
            messages.info(request, f"{user.username} n'est plus rattaché à une promotion.")
    elif action == "activer":
        if user == request.user:
            messages.error(request, "Tu ne peux pas désactiver ton propre compte.")
        else:
            user.is_active = not user.is_active
            user.save(update_fields=["is_active"])
            messages.success(request, f"Compte {'réactivé' if user.is_active else 'désactivé'}.")
    url = redirect("comptes:utilisateurs").url
    params = request.POST.get("retour", "")
    return redirect(f"{url}?{params}" if params else url)


# ---------- Candidatures reçues du site vitrine ----------

@admin_requis
def candidatures(request):
    from . import services
    from .models import Candidature
    if request.method == "POST":
        c = get_object_or_404(Candidature, pk=request.POST.get("candidature"))
        action = request.POST.get("action")
        if action == "accepter" and c.statut != Candidature.Statut.ACCEPTEE:
            promo = Promotion.objects.filter(pk=request.POST.get("promotion") or None, active=True).first()
            if not promo:
                messages.error(request, "Choisis la promotion dans laquelle inscrire la personne.")
            else:
                user, cree, envoye = services.accepter(request, c, promo)
                messages.success(request, f"{c.nom_complet} inscrit(e) à « {promo.nom} » "
                                          f"({'compte créé' if cree else 'compte existant'}, identifiant : {user.username}).")
                if not envoye:
                    messages.warning(request, "L'e-mail n'a pas pu partir : vérifie la configuration SMTP, "
                                              "puis utilise « Renvoyer l'invitation ».")
        elif action == "refuser" and c.statut == Candidature.Statut.NOUVELLE:
            services.refuser(request, c, (request.POST.get("motif") or "").strip())
            messages.info(request, f"Candidature de {c.nom_complet} refusée.")
        elif action == "renvoyer" and c.utilisateur:
            if services.envoyer_invitation(request, c.utilisateur, c.promotion):
                messages.success(request, f"Invitation renvoyée à {c.utilisateur.email}.")
            else:
                messages.error(request, "Échec de l'envoi de l'e-mail (configuration SMTP ?).")
        return redirect(f"{reverse('comptes:candidatures')}?statut={request.GET.get('statut', 'nouvelle')}")

    filtre = request.GET.get("statut", "nouvelle")
    qs = Candidature.objects.select_related("promotion", "utilisateur", "traitee_par")
    if filtre in Candidature.Statut.values:
        qs = qs.filter(statut=filtre)
    compte = {s: Candidature.objects.filter(statut=s).count() for s in Candidature.Statut.values}
    return render(request, "comptes/candidatures.html", {
        "candidatures": qs[:200], "filtre": filtre, "compte": compte, "statuts": Candidature.Statut.choices,
        "promotions": Promotion.objects.filter(active=True).select_related("formation").order_by("-date_debut")})
