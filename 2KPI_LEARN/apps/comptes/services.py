"""Traitement des candidatures reçues du site vitrine : création du compte, invitation, refus."""
import logging
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.text import slugify
from apps.core.permissions import APPRENANT, appliquer_role
from .models import Candidature, Profil

logger = logging.getLogger(__name__)
User = get_user_model()


def decouper_nom(nom_complet):
    """(prénom, nom) : un mot en MAJUSCULES est le nom de famille ; sinon « Prénom Nom… »."""
    mots = nom_complet.split()
    if not mots:
        return "", ""
    majuscules = [m for m in mots if m.isupper() and len(m) > 1]
    if majuscules and len(majuscules) < len(mots):
        return " ".join(m for m in mots if m not in majuscules), " ".join(majuscules)
    return mots[0], " ".join(mots[1:])


def identifiant_libre(email):
    base = slugify(email.split("@")[0]).replace("-", ".")[:30] or "apprenant"
    candidat, i = base, 1
    while User.objects.filter(username__iexact=candidat).exists():
        i += 1
        candidat = f"{base}{i}"
    return candidat


def _envoyer(sujet, gabarit, destinataire, contexte):
    try:
        send_mail(sujet, render_to_string(gabarit, contexte), settings.DEFAULT_FROM_EMAIL, [destinataire])
        return True
    except Exception:
        logger.warning("Échec d'envoi « %s » à %s", sujet, destinataire, exc_info=True)
        return False


def lien_definition_mdp(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return request.build_absolute_uri(reverse("password_reset_confirm", args=[uid, token]))


def envoyer_invitation(request, user, promotion=None):
    """E-mail de bienvenue avec lien pour définir son mot de passe (valable PASSWORD_RESET_TIMEOUT)."""
    from apps.core.models import Parametres
    return _envoyer(
        f"Bienvenue sur {Parametres.charger().nom_plateforme} - activez votre compte",
        "emails/invitation.txt", user.email,
        {"user": user, "promotion": promotion, "lien": lien_definition_mdp(request, user),
         "connexion": request.build_absolute_uri(reverse("login")),
         "jours": settings.PASSWORD_RESET_TIMEOUT // 86400})


def accuse_reception(candidature):
    return _envoyer("Nous avons bien reçu votre demande d'inscription", "emails/candidature_recue.txt",
                    candidature.email, {"c": candidature})


@transaction.atomic
def accepter(request, candidature, promotion):
    """Crée (ou retrouve par e-mail) le compte apprenant, l'inscrit à la promotion, envoie l'invitation.
    Retourne (utilisateur, compte_cree, email_envoye)."""
    from apps.comptes.views import _rattacher
    user = User.objects.filter(email__iexact=candidature.email).first()
    cree = user is None
    if cree:
        prenom, nom = decouper_nom(candidature.nom_complet)
        user = User.objects.create_user(identifiant_libre(candidature.email), candidature.email.lower(),
                                        first_name=prenom[:150], last_name=nom[:150])
        user.set_unusable_password()
        user.save(update_fields=["password"])
        appliquer_role(user, APPRENANT)
        profil = user.profil
        profil.telephone = candidature.telephone[:40]
        profil.save(update_fields=["telephone"])
    _rattacher(user, promotion)
    candidature.statut = Candidature.Statut.ACCEPTEE
    candidature.promotion = promotion
    candidature.utilisateur = user
    candidature.traitee_par = request.user
    candidature.traitee_le = timezone.now()
    candidature.save()
    envoye = envoyer_invitation(request, user, promotion) if (cree or not user.has_usable_password()) else \
        _envoyer("Vous êtes inscrit(e) à une nouvelle session", "emails/inscription_existant.txt", user.email,
                 {"user": user, "promotion": promotion, "connexion": request.build_absolute_uri(reverse("login"))})
    return user, cree, envoye


def refuser(request, candidature, motif=""):
    candidature.statut = Candidature.Statut.REFUSEE
    candidature.motif_refus = motif
    candidature.traitee_par = request.user
    candidature.traitee_le = timezone.now()
    candidature.save()
    return _envoyer("Votre demande d'inscription", "emails/candidature_refusee.txt", candidature.email,
                    {"c": candidature})


def notifier_admins(titre, message):
    from apps.agenda.models import Notification
    from apps.agenda.services import notifier
    from apps.core.permissions import ADMIN
    admins = [p.utilisateur for p in Profil.objects.filter(role=ADMIN, utilisateur__is_active=True)
              .select_related("utilisateur")]
    notifier(admins, titre=titre, message=message, type=Notification.Type.INFO)


@transaction.atomic
def creer_compte_apprenant(request, d):
    """Compte créé en libre-service depuis le site vitrine (CreationCompteForm.cleaned_data).
    Une session choisie devient une candidature, à accepter par l'admin comme celles de la vitrine."""
    user = User.objects.create_user(identifiant_libre(d["email"]), d["email"], d["password1"],
                                    first_name=d["first_name"].strip()[:150], last_name=d["last_name"].strip()[:150])
    appliquer_role(user, APPRENANT)
    profil = user.profil
    profil.categorie = d["categorie"]
    profil.telephone = d["telephone"].strip()[:40]
    profil.structure = d.get("structure", "").strip()[:200]
    profil.save(update_fields=["categorie", "telephone", "structure"])
    promo = d.get("promotion")
    if promo:
        Candidature.objects.create(
            nom_complet=user.get_full_name(), email=user.email, telephone=profil.telephone,
            message=f"Compte créé en ligne ({profil.get_categorie_display()}"
                    f"{', ' + profil.structure if profil.structure else ''}).",
            session_code=promo.code_vitrine, session_libelle=promo.nom, promotion=promo, utilisateur=user,
            ip=request.META.get("REMOTE_ADDR") or None)
    notifier_admins(f"Nouveau compte apprenant : {user.get_full_name()}",
                    f"{profil.get_categorie_display()} · {user.email} · {profil.telephone}"
                    + (f" · demande la session « {promo.nom} »" if promo else ""))
    transaction.on_commit(lambda: _envoyer(
        "Bienvenue sur 2KPI Learn - votre compte est créé", "emails/compte_cree.txt", user.email,
        {"user": user, "promotion": promo, "connexion": request.build_absolute_uri(reverse("login"))}))
    logger.info("Compte apprenant créé en libre-service : %s (%s)", user.username, user.email)
    return user


# ---------- Promotions d'un formateur ----------

def promotions_du_formateur(user):
    """Promotions où le formateur intervient : référent ou affecté par l'administration."""
    from apps.agenda.models import Promotion
    from django.db.models import Q
    return (Promotion.objects.filter(Q(formateur=user) | Q(affectations__formateur=user))
            .select_related("formation").distinct().order_by("-active", "-date_debut"))


@transaction.atomic
def definir_promotions_formateur(user, promotions, par):
    """Aligne les promotions d'un formateur sur la sélection de l'admin (formulaire du compte).
    Nouvelle promotion : affectation sur « tous les modules » (affinable module par module dans
    Promotions › Formateurs). Promotion décochée : affectation retirée et, s'il en était le référent,
    la promotion n'a plus de référent. Les affectations conservées gardent leurs modules.
    Retourne (ajoutées, retirées)."""
    from apps.agenda.models import Affectation, Notification
    from apps.agenda.services import notifier
    voulues = {p.pk: p for p in promotions}
    actuelles = {p.pk: p for p in promotions_du_formateur(user)}
    retirees = [p for pk, p in actuelles.items() if pk not in voulues]
    ajoutees = [p for pk, p in voulues.items() if pk not in actuelles]
    for p in retirees:
        Affectation.objects.filter(promotion=p, formateur=user).delete()
        if p.formateur_id == user.pk:
            p.formateur = None
            p.save(update_fields=["formateur"])
    for p in ajoutees:
        Affectation.objects.update_or_create(promotion=p, formateur=user,
                                             defaults={"tous_les_modules": True, "accordee_par": par})
    if ajoutees:
        noms = ", ".join(f"« {p.nom} »" for p in ajoutees)
        notifier([user], titre="Nouvelle(s) promotion(s) à encadrer",
                 message=f"L'administration t'a affecté à {noms} (tous les modules).",
                 type=Notification.Type.INFO, expediteur=par)
    if hasattr(user, "_interventions"):
        del user._interventions
    return ajoutees, retirees
