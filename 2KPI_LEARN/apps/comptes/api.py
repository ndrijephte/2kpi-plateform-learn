"""API publique appelée par le site vitrine : dépôt d'une candidature (inscription à une session).

POST /api/candidatures/  (JSON ou formulaire) — CORS limité à settings.VITRINE_ORIGINS,
champ piège anti-robots « site_web », limite de 5 envois par heure et par adresse IP.
"""
import json
import logging
from django import forms
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from apps.agenda.models import Notification, Promotion
from apps.agenda.services import notifier
from apps.core.permissions import ADMIN
from .models import Candidature, Profil
from .services import accuse_reception

logger = logging.getLogger(__name__)
LIMITE_PAR_HEURE = 5


class CandidatureApiForm(forms.Form):
    nom = forms.CharField(max_length=200)
    email = forms.EmailField()
    telephone = forms.CharField(max_length=40)
    participants = forms.IntegerField(min_value=1, max_value=100, required=False)
    message = forms.CharField(max_length=3000, required=False)
    session = forms.CharField(max_length=100, required=False)
    session_libelle = forms.CharField(max_length=250, required=False)
    site_web = forms.CharField(required=False)  # piège : invisible pour un humain


def _cors(request, reponse):
    origine = request.headers.get("Origin", "")
    if origine in settings.VITRINE_ORIGINS:
        reponse["Access-Control-Allow-Origin"] = origine
        reponse["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        reponse["Access-Control-Allow-Headers"] = "Content-Type"
        reponse["Access-Control-Max-Age"] = "86400"
        reponse["Vary"] = "Origin"
    return reponse


def _ip(request):
    return request.META.get("REMOTE_ADDR") or None


@csrf_exempt
def candidature(request):
    if request.method == "OPTIONS":
        return _cors(request, JsonResponse({}, status=204))
    if request.method != "POST":
        return _cors(request, JsonResponse({"ok": False, "erreur": "Méthode non autorisée."}, status=405))

    cle = f"candidature-ip-{_ip(request)}"
    if cache.get(cle, 0) >= LIMITE_PAR_HEURE:
        return _cors(request, JsonResponse(
            {"ok": False, "erreur": "Trop de demandes envoyées. Réessayez dans une heure."}, status=429))

    try:
        donnees = json.loads(request.body or b"{}") if request.content_type == "application/json" else request.POST
    except (ValueError, UnicodeDecodeError):
        return _cors(request, JsonResponse({"ok": False, "erreur": "Données illisibles."}, status=400))
    form = CandidatureApiForm(donnees)
    if not form.is_valid():
        return _cors(request, JsonResponse({"ok": False, "erreurs": form.errors.get_json_data()}, status=400))
    d = form.cleaned_data
    cache.set(cle, cache.get(cle, 0) + 1, 3600)
    if d["site_web"]:  # robot : on fait comme si tout allait bien
        return _cors(request, JsonResponse({"ok": True}, status=201))

    promo = (Promotion.objects.filter(code_vitrine=d["session"], active=True).first()
             if d["session"] else None)
    c = Candidature.objects.create(
        nom_complet=d["nom"].strip(), email=d["email"].strip().lower(), telephone=d["telephone"].strip(),
        participants=d["participants"] or 1, message=d["message"], session_code=d["session"],
        session_libelle=d["session_libelle"] or d["session"], promotion=promo, ip=_ip(request))
    admins = [p.utilisateur for p in Profil.objects.filter(role=ADMIN, utilisateur__is_active=True)
              .select_related("utilisateur")]
    notifier(admins, titre=f"Nouvelle candidature : {c.nom_complet}",
             message=f"{c.session_libelle or 'Session non précisée'} · {c.email} · {c.telephone}",
             type=Notification.Type.INFO)
    accuse_reception(c)
    logger.info("Candidature reçue #%s (%s)", c.pk, c.session_code)
    return _cors(request, JsonResponse({"ok": True}, status=201))
