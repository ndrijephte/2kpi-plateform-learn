import datetime as dt
import io
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from apps.agenda.models import Indisponibilite, Notification, Promotion
from apps.agenda.services import generer_agenda, synchroniser_agenda
from apps.core.test_utils import BaseTest


class AgendaTests(BaseTest):
    def test_creneau_parametre_et_jour_ferie_global(self):
        s = self.m1.seances.get(ordre=1)
        s.jour, s.heure_debut, s.semaine = 3, dt.time(18, 0), 1
        s.save()
        promo = type(self.promo_a).objects.create(formation=self.formation, nom="P", date_debut=dt.date(2026, 10, 5))
        Indisponibilite.objects.create(date_debut=dt.date(2026, 10, 8), motif="Férié")  # jeudi semaine 1, global
        generer_agenda(promo)
        ev = promo.evenements.get(seance=s)
        self.assertEqual(ev.date_debut.astimezone().date(), dt.date(2026, 10, 15))
        s.heure_debut = dt.time(19, 0)
        s.save()
        recales, _ = synchroniser_agenda(promo)
        ev.refresh_from_db()
        self.assertGreaterEqual(recales, 1)
        self.assertEqual(ev.date_debut.astimezone().hour, 19)

    def test_planning_reserve_aux_promotions_du_formateur(self):
        self.assertEqual(self.client_de(self.form_a).get(reverse("agenda:planning", args=[self.promo_b.pk])).status_code, 404)


class EnvoiNotificationsTests(BaseTest):
    url = "/agenda/notifications/envoyer/"

    def test_formateur_limite_a_ses_promotions(self):
        c = self.client_de(self.form_a)
        c.post(self.url, {"cible": "promotion", "promotion": self.promo_a.pk, "titre": "TP", "message": "x"})
        self.assertEqual(list(Notification.objects.filter(titre="TP").values_list("destinataire__username", flat=True)),
                         ["app_a"])
        for donnees in ({"cible": "promotion", "promotion": self.promo_b.pk}, {"cible": "tous"},
                        {"cible": "personnes", "destinataires": [self.app_b.pk]}):
            r = c.post(self.url, {**donnees, "titre": "X", "message": "y"})
            self.assertEqual(r.status_code, 200)
        self.assertFalse(Notification.objects.filter(titre="X").exists())

    def test_admin_tous_et_apprenant_refuse(self):
        self.client_de(self.admin).post(self.url, {"cible": "formateurs", "titre": "Réunion", "message": "y"})
        self.assertEqual(sorted(Notification.objects.filter(titre="Réunion")
                                .values_list("destinataire__username", flat=True)), ["form_a", "form_b"])
        self.assertEqual(self.client_de(self.app_a).get(self.url).status_code, 403)


@override_settings(VITRINE_ORIGINS=["https://www.2kpinnov.org"])
class CatalogueVitrineTests(BaseTest):
    api = "/api/sessions/"

    def test_api_publie_seulement_les_promotions_choisies_avec_places_calculees(self):
        self.promo_a.publiee_vitrine, self.promo_a.places_total, self.promo_a.places_hors_plateforme = True, 10, 3
        self.promo_a.save()  # code vitrine déduit du nom ; app_a y est déjà inscrit
        r = self.client.get(self.api, HTTP_ORIGIN="https://www.2kpinnov.org")
        self.assertEqual(r["Access-Control-Allow-Origin"], "https://www.2kpinnov.org")
        sessions = r.json()["sessions"]
        self.assertEqual([s["id"] for s in sessions], ["promo-a"])  # promo_b non publiée
        self.assertEqual((sessions[0]["placesTotal"], sessions[0]["placesRestantes"]), (10, 6))
        self.assertTrue(sessions[0]["dateAffichage"])  # date de début formatée
        self.insc_a.statut = "abandon"
        self.insc_a.save()
        self.assertEqual(self.client.get(self.api).json()["sessions"][0]["placesRestantes"], 7)
        self.assertNotIn("Access-Control-Allow-Origin", self.client.get(self.api, HTTP_ORIGIN="https://pirate.example"))

    def test_fiche_vitrine_reservee_admin_et_controle_des_places(self):
        url = reverse("agenda:fiche_vitrine", args=[self.promo_a.pk])
        self.assertEqual(self.client_de(self.form_a).get(url).status_code, 403)
        c = self.client_de(self.admin)
        base = {"publiee_vitrine": "on", "code_vitrine": "GeoAI Sassandra", "domaine": "Socle", "mode": "Hybride",
                "places_total": 5, "places_hors_plateforme": 9}
        self.assertEqual(c.post(url, base).status_code, 200)  # 9 > 5 : refusé
        self.assertRedirects(c.post(url, {**base, "places_hors_plateforme": 1}), reverse("agenda:promotions"))
        self.promo_a.refresh_from_db()
        self.assertEqual((self.promo_a.code_vitrine, self.promo_a.places_restantes), ("geoai-sassandra", 3))

    def test_import_des_sessions_du_site_idempotent(self):
        sortie = io.StringIO()
        call_command("importer_sessions_vitrine", stdout=sortie)
        call_command("importer_sessions_vitrine", stdout=sortie)
        p = Promotion.objects.get(code_vitrine="teledetection-sig-initiation")
        self.assertEqual((p.date_debut, p.places_restantes, p.publiee_vitrine), (dt.date(2026, 8, 10), 14, True))
        self.assertEqual(Promotion.objects.get(code_vitrine="collecte-donnees-terrain").date_affichage, "Tous les samedis")
        self.assertEqual(Promotion.objects.filter(publiee_vitrine=True).count(), 6)
