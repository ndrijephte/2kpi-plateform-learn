"""Données globales de l'interface : paramètres (logo, nom…), rôle, notifications, rubrique active."""
from django.templatetags.static import static
from .models import Parametres
from .permissions import ADMIN, APPRENANT, FORMATEUR, role_de

LIBELLES_ROLE = {APPRENANT: "Apprenant", FORMATEUR: "Formateur", ADMIN: "Administrateur"}

# url_name (ou app_name) -> rubrique de la barre latérale
RUBRIQUES = {
    "tableau_bord": "accueil",
    "formation": "cours",
    "evaluation": "cours",
    "evaluation:livrables": "livrables",
    "comptes": "profil",
    "comptes:utilisateurs": "utilisateurs",
    "comptes:utilisateur_editer": "utilisateurs",
    "core": "parametres",
    "formation:ressources": "ressources",
    "formation:ressource_ajouter": "ressources",
    "formation:ressource_modifier": "ressources",
    "agenda:mon_agenda": "agenda",
    "agenda:notifications": "notifications",
    "agenda:envoyer": "envoyer",
    "agenda:promotions": "promotions",
    "agenda:planning": "promotions",
    "agenda:presences": "promotions",
    "agenda:acces": "promotions",
}


def _rubrique(request):
    match = getattr(request, "resolver_match", None)
    if not match:
        return ""
    return RUBRIQUES.get(f"{match.app_name}:{match.url_name}") or RUBRIQUES.get(match.app_name, "")


def _identite():
    p = Parametres.charger()
    return {
        "parametres": p,
        "site_nom": f"{p.nom_plateforme} {p.suffixe}".strip(),
        "logo_url": p.logo.url if p.logo else "",
        "image_connexion_url": p.image_connexion.url if p.image_connexion else static("img/connexion.jpg"),
    }


def interface(request):
    user = request.user
    ctx = _identite()
    if not user.is_authenticated:
        return {**ctx, "notifs_non_lues": 0, "role": None, "rubrique": ""}
    from apps.agenda.models import Notification
    role = role_de(user)
    return {**ctx,
        "notifs_non_lues": Notification.objects.filter(destinataire=user, lu=False).count(),
        "role": role,
        "role_libelle": LIBELLES_ROLE.get(role, ""),
        "est_apprenant": role == APPRENANT,
        "est_formateur": role in (FORMATEUR, ADMIN),
        "est_admin": role == ADMIN,
        "rubrique": _rubrique(request),
    }
