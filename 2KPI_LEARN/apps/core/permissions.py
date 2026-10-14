"""Rôles et règles d'accès partagés par toutes les apps.

Trois profils :
- apprenant  : suit son cours, son agenda, ses notes ;
- formateur : anime SES promotions (planning, présences, correction) ;
- admin      : pilote toute la plateforme (utilisateurs, promotions, inscriptions).

Rien n'est accessible sans décision de l'administration :
- apprenant : inscription « en cours » rattachée à une promotion, puis module ouvert pour cette
  promotion (ouverture décidée par l'admin, ou automatique si l'admin l'a activée) — formation/acces.py ;
- formateur : référent d'une promotion (tous ses modules) ou affecté par l'admin à une promotion,
  sur les modules cochés (Affectation) — voir interventions().
"""
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q

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


def interventions(user):
    """Périmètre d'un formateur : {promotion_id: None (tous les modules) | {module_id, …}}.
    None pour un admin (tout), {} pour les autres rôles. Calculé une fois par requête."""
    role = role_de(user)
    if role == ADMIN:
        return None
    if role != FORMATEUR:
        return {}
    if not hasattr(user, "_interventions"):
        from apps.agenda.models import Affectation, Promotion
        perimetre = {pid: None for pid in Promotion.objects.filter(formateur=user).values_list("pk", flat=True)}
        for a in Affectation.objects.filter(formateur=user).prefetch_related("modules"):
            if a.tous_les_modules:
                perimetre[a.promotion_id] = None
            elif perimetre.get(a.promotion_id, set()) is not None:
                ids = {m.id for m in a.modules.all()}
                if ids:
                    perimetre.setdefault(a.promotion_id, set()).update(ids)
        user._interventions = perimetre
    return user._interventions


def q_interventions(user, promotion="promotion", module="seance__module"):
    """Filtre (Q) limitant un queryset aux couples (promotion, module) autorisés pour l'utilisateur.
    `promotion` / `module` : chemins des champs dans le queryset filtré."""
    perimetre = interventions(user)
    if perimetre is None:
        return Q()
    q = Q(pk__in=[])
    for pid, modules in perimetre.items():
        q |= Q(**{promotion: pid}) if modules is None else Q(**{promotion: pid, f"{module}__in": modules})
    return q


def promotions_visibles(user):
    """Promotions qu'un utilisateur peut piloter : toutes (admin) ou celles où l'admin l'a affecté."""
    from apps.agenda.models import Promotion
    perimetre = interventions(user)
    if perimetre is None:
        return Promotion.objects.all()
    return Promotion.objects.filter(pk__in=perimetre)


def pilote_promotion(user, promotion):
    """Calendrier, synchronisation : admin ou formateur référent de la promotion."""
    return role_de(user) == ADMIN or (promotion.formateur_id is not None and promotion.formateur_id == user.pk)


def modules_gerables(user):
    """Modules qu'un formateur peut consulter et enrichir (ressources) : ceux qui lui sont attribués."""
    from apps.formation.models import Module
    perimetre = interventions(user)
    if perimetre is None:
        return Module.objects.all()
    completes = [pid for pid, modules in perimetre.items() if modules is None]
    ids = set().union(*[m for m in perimetre.values() if m])
    return Module.objects.filter(Q(formation__promotions__in=completes) | Q(pk__in=ids)).distinct()


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
    """Formations où l'utilisateur intervient : toutes (admin) ou celles des promotions où l'admin
    l'a affecté — même si la formation n'a pas encore de module (« tous les modules » à venir)."""
    from apps.formation.models import Formation
    perimetre = interventions(user)
    if perimetre is None:
        return Formation.objects.all()
    return Formation.objects.filter(promotions__in=list(perimetre)).distinct()
