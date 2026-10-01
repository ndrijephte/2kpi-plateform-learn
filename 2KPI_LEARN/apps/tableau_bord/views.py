import datetime as dt
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone
from apps.agenda.models import Evenement, Promotion
from apps.comptes.models import Profil
from apps.core.permissions import ADMIN, APPRENANT, promotions_visibles, role_de
from apps.evaluation.models import Inscription, Livrable
from apps.evaluation.utils import inscription_courante
from apps.formation.acces import etats_modules
from apps.formation.models import Seance
from . import services


@login_required
def accueil(request):
    """Point d'entrée unique : chaque rôle a son propre tableau de bord."""
    role = role_de(request.user)
    if role == APPRENANT:
        return _apprenant(request)
    return _pilotage(request, admin=(role == ADMIN))


def _apprenant(request):
    user = request.user
    inscription = inscription_courante(user)
    ctx = {"inscription": inscription, "synthese": None, "a_venir": [], "reprendre": None,
           "notifications": user.notifications.filter(lu=False)[:3]}
    if inscription:
        ctx["synthese"] = services.synthese(inscription)
        if inscription.promotion_id:
            ctx["a_venir"] = list(
                inscription.promotion.evenements
                .filter(date_debut__gte=timezone.now())
                .exclude(statut=Evenement.Statut.ANNULE)
                .select_related("seance", "seance__module").order_by("date_debut")[:3])
        # Première séance sans livrable rendu = où reprendre
        rendus = Livrable.objects.filter(inscription=inscription, rendu=True).values("seance")
        # … parmi les modules ouverts pour l'apprenant uniquement
        etats = etats_modules(inscription, inscription.formation.modules.all())
        ouverts = [mid for mid, e in etats.items() if e.ouvert]
        ctx["reprendre"] = (Seance.objects.filter(module__formation=inscription.formation, module_id__in=ouverts)
                            .exclude(pk__in=rendus).select_related("module").first())
    return render(request, "tableau_bord/apprenant.html", ctx)


def _pilotage(request, admin):
    """Tableau de bord formateur ; l'admin y ajoute les indicateurs de la plateforme."""
    user = request.user
    maintenant = timezone.now()
    promos = promotions_visibles(user).filter(active=True)
    livrables = Livrable.objects.filter(rendu=True, note_sur_20__isnull=True,
                                        inscription__promotion__in=promos)
    semaine = maintenant + dt.timedelta(days=7)
    a_animer = (Evenement.objects.filter(promotion__in=promos, date_debut__gte=maintenant)
                .exclude(statut=Evenement.Statut.ANNULE)
                .select_related("promotion", "seance", "seance__module").order_by("date_debut"))
    ctx = {
        "promotions": (promos.select_related("formation", "formateur")
                       .annotate(nb_apprenants=Count("inscriptions", distinct=True),
                                 nb_evenements=Count("evenements", distinct=True))
                       .order_by("-date_debut")),
        "a_animer": a_animer[:5],
        "nb_semaine": a_animer.filter(date_debut__lte=semaine).count(),
        "nb_apprenants": Inscription.objects.filter(promotion__in=promos).count(),
        "nb_a_corriger": livrables.count(),
        "a_corriger": livrables.select_related("inscription__apprenant", "seance__module")
                               .order_by("seance__module__ordre", "seance__ordre")[:5],
        "notifications": user.notifications.filter(lu=False)[:3],
    }
    if admin:
        User = get_user_model()
        ctx["stats"] = {
            "apprenants": Profil.objects.filter(role=Profil.Role.APPRENANT, utilisateur__is_active=True).count(),
            "formateurs": Profil.objects.filter(role=Profil.Role.FORMATEUR, utilisateur__is_active=True).count(),
            "promotions": Promotion.objects.filter(active=True).count(),
            "inscriptions": Inscription.objects.filter(statut=Inscription.Statut.EN_COURS).count(),
        }
        ctx["sans_formateur"] = Promotion.objects.filter(active=True, formateur__isnull=True)
        ctx["sans_promotion"] = (User.objects.filter(profil__role=Profil.Role.APPRENANT, is_active=True)
                                 .exclude(inscriptions__promotion__isnull=False).count())
        ctx["derniers_comptes"] = User.objects.select_related("profil").order_by("-date_joined")[:5]
        return render(request, "tableau_bord/admin.html", ctx)
    return render(request, "tableau_bord/formateur.html", ctx)
