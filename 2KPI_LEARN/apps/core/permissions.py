"""Rôles et règles d'accès partagés par toutes les apps.

Trois profils :
- apprenant  : suit son cours, son agenda, ses notes ;
- formateur : anime SES promotions (planning, présences, correction) ;
- admin      : pilote toute la plateforme (utilisateurs, promotions, inscriptions).
"""
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

APPRENANT, FORMATEUR, ADMIN = "apprenant", "formateur", "admin"


def role_de(user):
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return ADMIN
    profil = getattr(user, "profil", None)
    return profil.role if profil else APPRENANT


def est_admin(user):
    return role_de(user) == ADMIN


def est_formateur(user):
    """Formateur OU admin (l'admin a tous les droits du formateur)."""
    return role_de(user) in (FORMATEUR, ADMIN)


def role_requis(*roles):
    """Vue réservée aux rôles donnés ; un utilisateur connecté sans droit reçoit une 403."""
    def decorateur(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if role_de(request.user) not in roles:
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return login_required(wrapper)
    return decorateur


formateur_requis = role_requis(FORMATEUR, ADMIN)
admin_requis = role_requis(ADMIN)


def promotions_visibles(user):
    """Promotions qu'un utilisateur peut piloter : toutes (admin) ou les siennes (formateur)."""
    from apps.agenda.models import Promotion
    qs = Promotion.objects.all()
    if role_de(user) == ADMIN:
        return qs
    if role_de(user) == FORMATEUR:
        return qs.filter(formateur=user)
    return qs.none()


GROUPE_ADMIN = "Administrateurs 2KPI"


def groupe_admin():
    """Groupe Django donnant aux administrateurs toutes les permissions de l'admin Django."""
    from django.contrib.auth.models import Group, Permission
    groupe, cree = Group.objects.get_or_create(name=GROUPE_ADMIN)
    if cree or groupe.permissions.count() != Permission.objects.count():
        groupe.permissions.set(Permission.objects.all())
    return groupe


def appliquer_role(user, role):
    """Change le rôle et synchronise l'accès à l'admin Django (is_staff + permissions)."""
    profil = user.profil
    profil.role = role
    profil.save(update_fields=["role"])
    staff = role == ADMIN or user.is_superuser
    if user.is_staff != staff:
        user.is_staff = staff
        user.save(update_fields=["is_staff"])
    if role == ADMIN:
        user.groups.add(groupe_admin())
    else:
        user.groups.remove(*user.groups.filter(name=GROUPE_ADMIN))


def formations_gerables(user):
    """Formations dont l'utilisateur gère les contenus : toutes (admin) ou celles de ses promotions."""
    from apps.formation.models import Formation
    role = role_de(user)
    if role == ADMIN:
        return Formation.objects.all()
    if role == FORMATEUR:
        return Formation.objects.filter(promotions__formateur=user).distinct()
    return Formation.objects.none()
