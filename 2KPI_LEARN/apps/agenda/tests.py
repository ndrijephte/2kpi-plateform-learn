import datetime as dt
import io
from decimal import Decimal
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from apps.agenda.models import AccesModule, Evenement, Indisponibilite, Notification, Promotion
from apps.agenda.services import generer_agenda, synchroniser_agenda
from apps.core.test_utils import BaseTest
from apps.evaluation.models import Inscription


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
        self.assertEqual(self.client.get(self.api).json()["sessions"], [])  # planifiée : jamais annoncée
        self.promo_a.statut = Promotion.Statut.INSCRIPTIONS
        self.promo_a.save()
        r = self.client.get(self.api, HTTP_ORIGIN="https://www.2kpinnov.org")
        self.assertEqual(r["Access-Control-Allow-Origin"], "https://www.2kpinnov.org")
        sessions = r.json()["sessions"]
        self.assertEqual([s["id"] for s in sessions], ["promo-a"])  # promo_b non publiée
        self.assertEqual((sessions[0]["placesTotal"], sessions[0]["placesRestantes"]), (10, 6))
        self.assertTrue(sessions[0]["dateAffichage"])  # date de début formatée
        self.assertFalse(sessions[0]["dateAConfirmer"])
        self.promo_a.date_debut = dt.date(2020, 1, 6)  # date passée : jamais affichée telle quelle
        self.promo_a.save()
        self.assertEqual(self.client.get(self.api).json()["sessions"][0]["dateAffichage"], "Date à confirmer")
        self.promo_a.date_debut = dt.date.today() + dt.timedelta(weeks=4)
        self.promo_a.save()
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
        self.assertEqual(c.post(url, {**base, "places_hors_plateforme": 1}).status_code, 200)  # promotion planifiée : refusé
        self.promo_a.statut = Promotion.Statut.INSCRIPTIONS
        self.promo_a.save()
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


class WorkflowTests(BaseTest):
    """Cycle de vie d'une promotion et des inscriptions : conditions, effets, journal."""

    def setUp(self):
        super().setUp()
        from apps.agenda import workflow
        self.wf = workflow
        self.P = Promotion.Statut
        self.S = Inscription.Statut
        # Nouvelle promotion de la même formation, sans apprenant
        self.promo = Promotion.objects.create(formation=self.formation, nom="Promo W", date_debut=self.promo_a.date_debut)

    def manques(self, promo, cible):
        return [c.libelle for c in self.wf.conditions_promotion(promo, cible) if not c.ok]

    def test_ouverture_exige_referent_et_calendrier(self):
        self.assertEqual(self.manques(self.promo, self.P.INSCRIPTIONS),
                         ["Formateur référent désigné", "Calendrier généré"])
        with self.assertRaises(self.wf.TransitionRefusee):
            self.wf.changer_statut_promotion(self.promo, self.P.INSCRIPTIONS, self.admin)
        self.promo.formateur = self.form_a
        self.promo.save()
        generer_agenda(self.promo)
        self.wf.changer_statut_promotion(self.promo, self.P.INSCRIPTIONS, self.admin)
        self.assertEqual(self.promo.statut, self.P.INSCRIPTIONS)
        self.assertEqual(self.promo.journal.first().par, self.admin)
        with self.assertRaises(self.wf.TransitionRefusee):  # pas de saut d'étape
            self.wf.changer_statut_promotion(self.promo, self.P.CLOTUREE, self.admin)

    def _promo_ouverte_avec(self, apprenant):
        self.promo.formateur = self.form_a
        self.promo.statut = self.P.INSCRIPTIONS
        self.promo.publiee_vitrine = True
        self.promo.save()
        generer_agenda(self.promo)
        return Inscription.objects.create(apprenant=apprenant, formation=self.formation, promotion=self.promo)

    def test_confirmation_exige_le_paiement_et_ouvre_l_acces(self):
        from apps.formation.acces import etats_modules
        apprenant = self.compte("app_w", "apprenant")
        insc = self._promo_ouverte_avec(apprenant)
        AccesModule.objects.create(promotion=self.promo, module=self.m1, etat=AccesModule.Etat.OUVERT)
        self.assertEqual(insc.statut, self.S.ADMISE)
        self.assertFalse(etats_modules(insc, [self.m1])[self.m1.id].ouvert)  # admise : pas encore d'accès
        self.assertEqual(self.manques(self.promo, self.P.PRETE), ["Au moins 1 inscription confirmée"])
        with self.assertRaises(self.wf.TransitionRefusee):
            self.wf.changer_statut_inscription(insc, self.S.CONFIRMEE, self.admin)
        insc.paiement = Inscription.Paiement.RECU
        self.wf.changer_statut_inscription(insc, self.S.CONFIRMEE, self.admin)
        self.assertTrue(etats_modules(insc, [self.m1])[self.m1.id].ouvert)
        self.assertTrue(apprenant.notifications.filter(titre__startswith="Inscription confirmée").exists())
        # Prête : la vitrine reste publiée ; au démarrage, elle est retirée et l'inscription passe en cours
        self.wf.changer_statut_promotion(self.promo, self.P.PRETE, self.admin)
        self.assertTrue(self.promo.publiee_vitrine)
        self.assertIn("Date de début atteinte", self.manques(self.promo, self.P.EN_COURS))
        self.promo.date_debut = timezone.localdate()
        self.promo.save()
        demarrees, _ = self.wf.demarrages_du_jour()
        self.assertEqual(demarrees, [self.promo])
        self.promo.refresh_from_db()
        insc.refresh_from_db()
        self.assertEqual((self.promo.statut, self.promo.publiee_vitrine, insc.statut), (self.P.EN_COURS, False, self.S.EN_COURS))
        self.assertIsNone(self.promo.journal.filter(vers=self.P.EN_COURS).first().par)  # automatique

    def test_abandon_et_derogation_exigent_un_motif(self):
        with self.assertRaises(self.wf.TransitionRefusee):
            self.wf.changer_statut_inscription(self.insc_a, self.S.ABANDON, self.admin)
        self.wf.changer_statut_inscription(self.insc_a, self.S.ABANDON, self.admin, motif="Déménagement")
        self.assertEqual(self.insc_a.journal.first().motif, "Déménagement")
        with self.assertRaises(self.wf.TransitionRefusee):  # « validée » est réservé à la clôture
            self.wf.changer_statut_inscription(self.insc_b, self.S.VALIDEE, self.admin, motif="x")

    def test_cloture_calcule_les_resultats_80_pourcent_et_10_sur_20(self):
        from apps.evaluation import grille
        from apps.evaluation.models import Livrable, Presence, Soutenance
        promo = self.promo_a
        promo.statut = self.P.EN_COURS
        promo.save()
        app_c = self.compte("app_c", "apprenant")
        insc_c = Inscription.objects.create(apprenant=app_c, formation=self.formation, promotion=promo, statut=self.S.EN_COURS)
        evenements = list(promo.evenements.order_by("date_debut"))
        self.assertIn("Toutes les séances sont réalisées ou annulées", self.manques(promo, self.P.CLOTUREE))
        promo.evenements.exclude(pk__in=[e.pk for e in evenements[:5]]).update(statut=Evenement.Statut.ANNULE)
        promo.evenements.filter(pk__in=[e.pk for e in evenements[:5]]).update(statut=Evenement.Statut.REALISE)
        self.assertIn("Présences saisies pour chaque séance réalisée", self.manques(promo, self.P.CLOTUREE))
        for n, ev in enumerate(evenements[:5]):  # A : 4/5 présent (80 %) ; C : 3/5 (60 %)
            Presence.objects.create(inscription=self.insc_a, evenement=ev,
                                    statut=Presence.Statut.ABSENT if n == 4 else Presence.Statut.PRESENT)
            Presence.objects.create(inscription=insc_c, evenement=ev,
                                    statut=Presence.Statut.PRESENT if n < 3 else Presence.Statut.ABSENT)
        livrable = Livrable.objects.create(inscription=self.insc_a, seance=evenements[0].seance, rendu=True)
        self.assertEqual(self.manques(promo, self.P.CLOTUREE), ["Évaluation finale complète (grille du projet, soutenance)",
                                                                 "Tous les livrables rendus sont notés"])
        livrable.note_sur_20 = 12
        livrable.save()
        # Note A = 0,4 × 12 + 0,4 × 10 + 0,2 × 11 = 11 ; C : bonnes notes mais assiduité insuffisante
        criteres = list(self.formation.criteres.all())
        grille.enregistrer_notes(self.insc_a, {c.pk: Decimal(10) for c in criteres})
        grille.enregistrer_notes(insc_c, {c.pk: Decimal(18) for c in criteres[:-1]})
        Soutenance.objects.create(inscription=self.insc_a, note_sur_20=11)
        Soutenance.objects.create(inscription=insc_c, note_sur_20=18)
        self.assertEqual(self.manques(promo, self.P.CLOTUREE), ["Évaluation finale complète (grille du projet, soutenance)"])
        grille.enregistrer_notes(insc_c, {criteres[-1].pk: Decimal(18)})
        admise = Inscription.objects.create(apprenant=self.compte("app_d", "apprenant"), formation=self.formation,
                                            promotion=promo)
        self.wf.changer_statut_promotion(promo, self.P.CLOTUREE, self.admin)
        for i in (self.insc_a, insc_c, admise):
            i.refresh_from_db()
        self.assertEqual((self.insc_a.statut, self.insc_a.taux_assiduite, self.insc_a.note_finale),
                         (self.S.VALIDEE, 80, Decimal("11.00")))
        self.assertEqual((insc_c.statut, insc_c.taux_assiduite), (self.S.NON_VALIDEE, 60))
        self.assertEqual(admise.statut, self.S.ABANDON)
        self.assertTrue(self.app_a.notifications.filter(titre__startswith="Résultat").exists())
        # Dérogation motivée, puis archivage (la promotion n'est plus « active ») et désarchivage
        self.wf.changer_statut_inscription(insc_c, self.S.VALIDEE, self.admin, motif="Absences justifiées (santé)")
        self.wf.changer_statut_promotion(promo, self.P.ARCHIVEE, self.admin)
        self.assertFalse(Promotion.objects.get(pk=promo.pk).active)
        self.wf.desarchiver(promo, self.admin)
        self.assertEqual((promo.statut, promo.active), (self.P.CLOTUREE, True))

    def test_annulation_refusee_avec_inscrits_confirmes(self):
        self.promo_b.statut = self.P.PRETE
        self.promo_b.save()
        self.assertEqual(self.manques(self.promo_b, self.P.ARCHIVEE), ["Aucune inscription confirmée"])

    def test_page_pilotage(self):
        url = reverse("agenda:pilotage", args=[self.promo_a.pk])
        c = self.client_de(self.admin)
        r = c.get(url)
        self.assertContains(r, "Ouvrir les inscriptions")
        self.assertContains(r, "Conditions manquantes")  # annulation : app_a y suit déjà la formation
        r = c.post(url, {"action": "promotion", "cible": self.P.INSCRIPTIONS}, follow=True)
        self.promo_a.refresh_from_db()
        self.assertEqual(self.promo_a.statut, self.P.INSCRIPTIONS)
        # Formateur : consultation de SES promotions, aucune décision
        f = self.client_de(self.form_a)
        self.assertEqual(f.get(url).status_code, 200)
        self.assertEqual(f.post(url, {"action": "promotion", "cible": self.P.PLANIFIEE}).status_code, 403)
        self.assertEqual(f.get(reverse("agenda:pilotage", args=[self.promo_b.pk])).status_code, 404)
        self.assertEqual(self.client_de(self.app_a).get(url).status_code, 403)


class PresencesObligatoiresTests(BaseTest):
    """Une séance n'est réalisée qu'avec sa feuille de présence ; les oublis sont relancés."""

    def setUp(self):
        super().setUp()
        self.promo_a.statut = Promotion.Statut.EN_COURS
        self.promo_a.save()
        self.ev = self.promo_a.evenements.filter(seance__module=self.m1).order_by("date_debut").first()
        self.ev.date_debut = timezone.now() - dt.timedelta(days=2)
        self.ev.save()
        self.admise = Inscription.objects.create(apprenant=self.compte("app_x", "apprenant"),
                                                 formation=self.formation, promotion=self.promo_a)
        self.c = self.client_de(self.form_a)

    def test_realisee_refusee_sans_presences_puis_feuille_realise(self):
        action = reverse("agenda:evenement_action", args=[self.ev.pk])
        self.assertRedirects(self.c.post(action, {"action": "realiser"}), reverse("agenda:presences", args=[self.ev.pk]))
        self.ev.refresh_from_db()
        self.assertEqual(self.ev.statut, Evenement.Statut.PLANIFIE)
        page = self.c.get(reverse("agenda:presences", args=[self.ev.pk]))
        self.assertEqual([l["inscription"] for l in page.context["lignes"]], [self.insc_a])  # admise : pas pointée
        self.c.post(reverse("agenda:presences", args=[self.ev.pk]), {f"statut_{self.insc_a.pk}": "present"})
        self.ev.refresh_from_db()
        self.assertEqual(self.ev.statut, Evenement.Statut.REALISE)

    def test_seance_future_ni_realisee_ni_pointee(self):
        futur = self.promo_a.evenements.filter(date_debut__gt=timezone.now()).first()
        self.c.post(reverse("agenda:evenement_action", args=[futur.pk]), {"action": "realiser"})
        futur.refresh_from_db()
        self.assertEqual(futur.statut, Evenement.Statut.PLANIFIE)
        self.assertEqual(self.c.get(reverse("agenda:presences", args=[futur.pk])).status_code, 302)

    def test_relances_formateur_puis_admin_une_seule_fois(self):
        from apps.agenda.workflow import relances_presences
        self.assertEqual(relances_presences(), (1, 0))  # J+2 : formateur seulement
        self.assertTrue(self.form_a.notifications.filter(evenement=self.ev, titre__startswith="Présences à saisir").exists())
        self.assertFalse(self.form_b.notifications.filter(titre__startswith="Présences").exists())
        self.assertEqual(relances_presences(), (0, 0))  # pas de doublon
        self.assertEqual(relances_presences(timezone.now() + dt.timedelta(days=2)), (0, 1))  # J+4 : admins
        self.assertTrue(self.admin.notifications.filter(titre__startswith="Présences non saisies").exists())
        tableau = self.c.get(reverse("tableau_bord:accueil"))
        self.assertEqual(tableau.context["a_pointer"], [self.ev])
        self.assertContains(self.c.get(reverse("agenda:planning", args=[self.promo_a.pk])), "Présences à saisir")
