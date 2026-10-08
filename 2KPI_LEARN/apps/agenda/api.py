"""API publique lue par le site vitrine : catalogue des sessions ouvertes.

GET /api/sessions/ — promotions actives publiées sur la vitrine, au format attendu par
VITRINE_2KPI/js/sessions-data.js. Lecture seule, données publiques ; CORS limité à
settings.VITRINE_ORIGINS, jamais mis en cache pour que les places restent exactes.
"""
from django.db.models import Count, Q
from django.http import JsonResponse
from django.utils.formats import date_format
from django.views.decorators.http import require_http_methods
from apps.comptes.api import _cors
from .models import Promotion


def fiche(p, inscrits):
    restantes = max(0, p.places_total - inscrits - p.places_hors_plateforme)
    return {
        "id": p.code_vitrine,
        "titre": p.nom,
        "domaine": p.domaine,
        "mode": p.mode,
        "dateAffichage": p.date_affichage or date_format(p.date_debut, "j F Y"),
        "dateDebut": p.date_debut.isoformat(),
        "horaire": p.horaire,
        "duree": p.duree,
        "lieu": p.lieu or ("En ligne (visioconférence)" if p.mode == Promotion.Mode.EN_LIGNE else ""),
        "placesTotal": p.places_total,
        "placesRestantes": restantes,
        "prix": p.prix,
        "description": p.description_vitrine or p.formation.description[:300],
    }


@require_http_methods(["GET", "HEAD", "OPTIONS"])
def sessions(request):
    if request.method == "OPTIONS":
        return _cors(request, JsonResponse({}, status=204))
    promos = (Promotion.objects.filter(active=True, publiee_vitrine=True).exclude(code_vitrine="")
              .select_related("formation")
              .annotate(nb_inscrits=Count("inscriptions", filter=~Q(inscriptions__statut="abandon")))
              .order_by("date_debut", "nom"))
    reponse = JsonResponse({"sessions": [fiche(p, p.nb_inscrits) for p in promos]},
                           json_dumps_params={"ensure_ascii": False})
    reponse["Cache-Control"] = "no-cache"  # places restantes exactes à chaque affichage
    return _cors(request, reponse)
