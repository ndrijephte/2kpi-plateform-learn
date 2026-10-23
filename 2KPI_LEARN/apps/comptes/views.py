import logging
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from apps.agenda.models import Promotion
from apps.formation.acces import diagnostic_apprenant
from apps.core.permissions import ADMIN, FORMATEUR, admin_requis, appliquer_role, role_de
from apps.evaluation.models import Inscription
from apps.evaluation.utils import inscription_courante
from .forms import (CompteAdminForm, CompteForm, CreationCompteForm, MotDePasseOublieForm, NouvelUtilisateurForm,
                    PrerequisForm, ProfilForm)
from .models import Profil

User = get_user_model()
logger = logging.getLogger(__name__)


@login_required
def profil(request):
    # Les comptes créés avant le signal (ex. createsuperuser initial) n'ont pas toujours de profil.
    from apps.evaluation.grille import OK, etats_prerequis
    from apps.evaluation.models import PrerequisInscription
    profil = _profil_complet(request.user)
    inscription = inscription_courante(request.user) if role_de(request.user) == "apprenant" else None
    libelles = dict(PrerequisInscription.Statut.choices)
    items = [(p.libelle + (" (obligatoire)" if p.obligatoire else ""), statut, libelles[statut])
             for p, statut in etats_prerequis(inscription)]
    from .services import promotions_du_formateur
    formateur = role_de(request.user) == FORMATEUR
    return render(request, "comptes/profil.html", {
        "profil": profil, "prerequis": items, "prerequis_ok": sum(1 for _, v, _ in items if v == OK),
        "inscription": inscription,
        "promotions_encadrees": promotions_du_formateur(request.user) if formateur else None,
    })


def _profil_complet(user):
    return Profil.objects.get_or_create(utilisateur=user)[0]


def _prerequis_form(data, user):
    """Formulaire des prérequis de l'inscription courante d'un apprenant (None s'il n'y en a pas)."""
    if role_de(user) != "apprenant":
        return None
    insc = inscription_courante(user)
    if insc is None or not insc.formation.prerequis.exists():
        return None
    return PrerequisForm(data, inscription=insc, prefix="r")


@login_required
def profil_modifier(request):
    """Chaque utilisateur (admin compris) modifie ses propres informations."""
    user = request.user
    profil = _profil_complet(user)
    data, files = (request.POST, request.FILES) if request.method == "POST" else (None, None)
    compte_form = CompteForm(data, instance=user, prefix="c")
    profil_form = ProfilForm(data, files, instance=profil, prefix="p", role=role_de(user))
    prerequis_form = _prerequis_form(data, user)
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
    """L'admin modifie toutes les informations d'un compte (le sien compris). Les champs dépendent
    du rôle : promotion pour un apprenant, promotions encadrées pour un formateur."""
    from .services import definir_promotions_formateur, promotions_du_formateur
    cible = get_object_or_404(User, pk=pk)
    profil = _profil_complet(cible)
    insc = inscription_courante(cible)
    data, files = (request.POST, request.FILES) if request.method == "POST" else (None, None)
    compte_form = CompteAdminForm(data, instance=cible, prefix="c",
                                  initial={"role": role_de(cible), "promotion": insc.promotion_id if insc else None,
                                           "promotions_formateur": list(promotions_du_formateur(cible))
                                           if role_de(cible) == FORMATEUR else []})
    profil_form = ProfilForm(data, files, instance=profil, prefix="p")
    profil_form.masquer_hors_role(compte_form.data.get("c-role") if data else role_de(cible))
    prerequis_form = _prerequis_form(data, cible)
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
                role = cible.profil.role  # un super-utilisateur reste administrateur
                if role == Profil.Role.APPRENANT:
                    promo = compte_form.cleaned_data["promotion"]
                    if promo:
                        _rattacher(cible, promo)
                elif role == Profil.Role.FORMATEUR:
                    definir_promotions_formateur(cible, compte_form.cleaned_data["promotions_formateur"],
                                                 request.user)
            if cible == request.user and compte_form.cleaned_data["nouveau_mdp"]:
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, cible)
            messages.success(request, f"Compte « {cible.username} » mis à jour.")
            return redirect("comptes:utilisateurs")
    return render(request, "comptes/profil_form.html", {
        "compte_form": compte_form, "profil_form": profil_form, "prerequis_form": prerequis_form,
        "cible": cible, "soi": cible == request.user,
        "diagnostic": diagnostic_apprenant(cible) if role_de(cible) == Profil.Role.APPRENANT else None,
        "retour_url": reverse("comptes:utilisateurs"), "retour_label": "Utilisateurs"})


def _rattacher(user, promotion):
    """Inscrit l'apprenant à la formation de la promotion et le rattache à celle-ci. Une nouvelle
    inscription est « admise » : elle donne accès aux contenus une fois confirmée (workflow)."""
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
            elif d["role"] == Profil.Role.FORMATEUR and d["promotions_formateur"]:
                from .services import definir_promotions_formateur
                definir_promotions_formateur(user, d["promotions_formateur"], request.user)
        messages.success(request, f"Compte « {user.username} » créé ({user.profil.get_role_display()}).")
        return redirect("comptes:utilisateurs")

    filtre, q = request.GET.get("role", ""), request.GET.get("q", "").strip()
    qs = User.objects.select_related("profil").prefetch_related(
        "inscriptions__promotion", "promotions_encadrees", "affectations__promotion").order_by(
        "-is_active", "last_name", "first_name", "username")
    if filtre in Profil.Role.values:
        qs = qs.filter(profil__role=filtre)
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(first_name__icontains=q)
                       | Q(last_name__icontains=q) | Q(email__icontains=q))
    lignes = []
    for u in qs:
        role = role_de(u)
        insc = inscription_courante(u) if role == Profil.Role.APPRENANT else None
        diag = diagnostic_apprenant(u) if role == Profil.Role.APPRENANT else None
        blocage = next((d for ok, _, d in diag["etapes"] if not ok), "") if diag else ""
        encadrees = []
        if role == FORMATEUR:  # référent d'abord, puis affectations (module par module ou toutes)
            encadrees = [(p, True) for p in u.promotions_encadrees.all()]
            vues = {p.pk for p, _ in encadrees}
            encadrees += [(a.promotion, False) for a in u.affectations.all() if a.promotion_id not in vues]
        lignes.append({"u": u, "role": role, "promotion": insc.promotion if insc else None,
                       "encadrees": encadrees, "blocage": blocage})
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
            promo = Promotion.objects.filter(pk=request.POST.get("promotion") or None,
                                             statut__in=Promotion.STATUTS_ADMISSION).first()
            if not promo:
                messages.error(request, "Choisis une promotion qui accepte des inscriptions "
                                        "(inscriptions ouvertes, prête ou en cours).")
            else:
                user, cree, envoye = services.accepter(request, c, promo)
                messages.success(request, f"{c.nom_complet} admis(e) dans « {promo.nom} » "
                                          f"({'compte créé' if cree else 'compte existant'}, identifiant : {user.username}). "
                                          "Confirme l'inscription dans Promotions › Pilotage dès le paiement reçu.")
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

    from .models import Interet
    filtre = request.GET.get("statut", "nouvelle")
    interets_par_formation = []
    if filtre == "interets":
        groupes = {}
        for i in Interet.objects.select_related("formation").order_by("formation__titre", "prevenu_le", "-date"):
            groupes.setdefault(i.formation, []).append(i)
        interets_par_formation = [{"formation": f, "liste": l, "en_attente": [i for i in l if not i.prevenu_le]}
                                  for f, l in groupes.items()]
    qs = Candidature.objects.select_related("promotion", "utilisateur", "traitee_par")
    if filtre in Candidature.Statut.values:
        qs = qs.filter(statut=filtre)
    compte = {s: Candidature.objects.filter(statut=s).count() for s in Candidature.Statut.values}
    return render(request, "comptes/candidatures.html", {
        "candidatures": qs[:200], "filtre": filtre, "compte": compte, "statuts": Candidature.Statut.choices,
        "interets_par_formation": interets_par_formation,
        "nb_interets": Interet.objects.filter(prevenu_le__isnull=True).count(),
        "promotions": Promotion.objects.filter(statut__in=Promotion.STATUTS_ADMISSION)
                               .select_related("formation").order_by("-date_debut")})


def creer_compte(request):
    """Création de compte apprenant / étudiant en libre-service (lien « Créer mon compte » de la vitrine).
    ?session=<code vitrine> présélectionne la session demandée."""
    from django.contrib.auth import login
    from . import services
    if request.user.is_authenticated:
        return redirect("tableau_bord:accueil")
    code = request.GET.get("session", "")
    form = CreationCompteForm(request.POST or None, initial={
        "promotion": Promotion.objects.filter(code_vitrine=code, active=True, publiee_vitrine=True).first()
        if code else None})
    if request.method == "POST" and form.is_valid():
        if form.cleaned_data["site_web"]:  # robot : on ne crée rien
            return redirect("login")
        cle = f"creation-compte-ip-{request.META.get('REMOTE_ADDR')}"
        if cache.get(cle, 0) >= CREATIONS_PAR_HEURE:
            messages.error(request, "Trop de comptes créés depuis cette connexion. Réessayez dans une heure.")
        else:
            cache.set(cle, cache.get(cle, 0) + 1, 3600)
            user = services.creer_compte_apprenant(request, form.cleaned_data)
            login(request, user, backend="apps.comptes.backends.IdentifiantOuEmailBackend")
            messages.success(request, f"Bienvenue {user.first_name} ! Votre compte est créé "
                                      f"(identifiant : {user.username}, ou votre e-mail).")
            return redirect("tableau_bord:accueil")
    return render(request, "registration/creer_compte.html", {"form": form})


CREATIONS_PAR_HEURE = 5


class MotDePasseOublieView(auth_views.PasswordResetView):
    """Limite les demandes (3 par heure et par adresse e-mail, 10 par adresse IP) contre l'envoi massif
    d'e-mails ; la page de confirmation reste identique pour ne pas révéler quels comptes existent."""
    form_class = MotDePasseOublieForm
    LIMITE_PAR_EMAIL, LIMITE_PAR_IP = 3, 10

    def form_valid(self, form):
        email = form.cleaned_data["email"].strip().lower()
        cles = {f"mdp-oublie-ip-{self.request.META.get('REMOTE_ADDR')}": self.LIMITE_PAR_IP,
                f"mdp-oublie-email-{email}": self.LIMITE_PAR_EMAIL}
        compteurs = {cle: cache.get(cle, 0) for cle in cles}
        for cle in cles:
            cache.set(cle, compteurs[cle] + 1, 3600)
        if any(compteurs[cle] >= limite for cle, limite in cles.items()):
            logger.warning("Mot de passe oublié : limite horaire atteinte (%s, IP %s) - rien n'est envoyé",
                           email, self.request.META.get("REMOTE_ADDR"))
            return redirect(self.get_success_url())
        return super().form_valid(form)
