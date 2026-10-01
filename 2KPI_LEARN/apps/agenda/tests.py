import datetime as dt
from django.urls import reverse
from apps.agenda.models import Indisponibilite, Notification
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
