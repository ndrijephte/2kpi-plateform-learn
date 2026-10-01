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
        f"Bienvenue sur {Parametres.charger().nom_plateforme} — activez votre compte",
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
