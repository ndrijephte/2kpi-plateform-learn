import datetime as dt
from decimal import Decimal
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

    def test_message_mis_en_forme_et_module_concerne(self):
        c = self.client_de(self.form_a)
        c.post(self.url, {"cible": "promotion", "promotion": self.promo_a.pk, "titre": "Consignes TP",
                          "module": self.m1.pk, "par_email": "on",
                          "message": '<p><b>Important</b> <span style="color:red">à lire</span></p>'
                                     '<ul><li>Point 1</li><li>Point 2</li></ul><img src=x onerror=alert(1)>'
                                     '<a href="javascript:alert(1)">piège</a><a href="https://2kpinnov.org">site</a>'})
        n = Notification.objects.get(titre="Consignes TP")
        self.assertEqual(n.message, '<p><b>Important</b> à lire</p><ul><li>Point 1</li><li>Point 2</li></ul>piège'
                                    '<a href="https://2kpinnov.org" target="_blank" rel="noopener noreferrer">site</a>')
        self.assertEqual(n.module, self.m1)
        self.assertEqual(n.destination, self.m1.get_absolute_url())
        from django.core import mail
        self.assertIn("- Point 1\n- Point 2", mail.outbox[-1].body)
        r = self.client_de(self.app_a).get("/agenda/notifications/")
        self.assertContains(r, "<b>Important</b>", html=False)
        self.assertContains(r, f"Ouvrir le module {self.m1.code}")
        # Un message vide (seulement des balises) est refusé
        r = c.post(self.url, {"cible": "promotion", "promotion": self.promo_a.pk, "titre": "Vide", "message": "<p><br></p>"})
        self.assertFalse(Notification.objects.filter(titre="Vide").exists())


class OuvertureNotificationTests(BaseTest):
    def test_clic_marque_lue_et_ouvre_la_page_concernee(self):
        from .services import notifier
        n, = notifier([self.app_a], titre="Module ouvert", message="", module=self.m1, envoyer_email=False)
        r = self.client_de(self.app_a).get(reverse("agenda:notification", args=[n.pk]))
        self.assertRedirects(r, self.m1.get_absolute_url(), fetch_redirect_response=False)
        n.refresh_from_db()
        self.assertTrue(n.lu)
        lien, = notifier([self.app_a], titre="Lien", message="", lien="/agenda/", envoyer_email=False)
        self.assertRedirects(self.client_de(self.app_a).get(reverse("agenda:notification", args=[lien.pk])),
                             "/agenda/", fetch_redirect_response=False)
        # Lien externe ignoré, notification sans cible : retour à la liste
        externe, = notifier([self.app_a], titre="Ext", message="", lien="//exemple.org", envoyer_email=False)
        self.assertRedirects(self.client_de(self.app_a).get(reverse("agenda:notification", args=[externe.pk])),
                             reverse("agenda:notifications"), fetch_redirect_response=False)
        # La notification d'un autre utilisateur reste inaccessible
        self.assertEqual(self.client_de(self.app_b).get(reverse("agenda:notification", args=[n.pk])).status_code, 404)


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
        self.promo_a.prix = "150 000 FCFA"
        self.promo_a.save()
        self.assertEqual(self.client.get(self.api).json()["sessions"][0]["prix"], "")  # masqué par défaut
        self.promo_a.afficher_prix = True
        self.promo_a.save()
        self.assertEqual(self.client.get(self.api).json()["sessions"][0]["prix"], "150 000 FCFA")
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

    def fiche(self, promo, **extra):
        """Données complètes du formulaire de session (tous les champs, comme le navigateur les envoie)."""
        return {"nom": promo.nom, "date_debut": promo.date_debut.isoformat(), "formateur": promo.formateur_id or "",
                "mode": "En ligne", "places_total": 20, "domaine": "Socle", "code_vitrine": promo.code_vitrine,
                "places_hors_plateforme": 0, "effectif_minimum": 1, **extra}

    def test_fiche_vitrine_reservee_admin_et_controle_des_places(self):
        url = reverse("agenda:fiche_vitrine", args=[self.promo_a.pk])
        self.assertEqual(self.client_de(self.form_a).get(url).status_code, 403)
        c = self.client_de(self.admin)
        base = self.fiche(self.promo_a, code_vitrine="GeoAI Sassandra", mode="Hybride",
                          places_total=5, places_hors_plateforme=9)
        self.assertEqual(c.post(url, base).status_code, 200)  # 9 > 5 : refusé
        self.assertRedirects(c.post(url, {**base, "places_hors_plateforme": 1}), reverse("agenda:promotions"))
        self.promo_a.refresh_from_db()
        self.assertEqual((self.promo_a.code_vitrine, self.promo_a.places_restantes), ("geoai-sassandra", 3))

    def test_assistant_nouvelle_session_et_publication(self):
        url = reverse("agenda:session_nouvelle")
        self.assertEqual(self.client_de(self.form_a).get(url).status_code, 403)
        c = self.client_de(self.admin)
        r = c.get(url)
        self.assertContains(r, "Créer et publier")
        self.assertContains(r, "Aperçu sur 2kpinnov.org")
        debut = dt.date.today() + dt.timedelta(weeks=6)
        donnees = {"formation": self.formation.pk, "date_debut": debut.isoformat(), "nom": "", "formateur": "",
                   "mode": "En ligne", "places_total": 15, "domaine": "Socle", "code_vitrine": "",
                   "places_hors_plateforme": 0, "effectif_minimum": 1}
        # Sans référent : enregistrée en brouillon (nom proposé, calendrier généré), publication refusée
        r = c.post(url, {**donnees, "action": "publier"})
        from django.utils.formats import date_format
        nom = f"{self.formation.titre} - Session de {date_format(debut, 'F Y')}"
        promo = Promotion.objects.get(nom=nom)
        self.assertRedirects(r, reverse("agenda:fiche_vitrine", args=[promo.pk]))
        self.assertEqual((promo.statut, promo.publiee_vitrine, promo.etat_session[0]), ("planifiee", False, "Brouillon"))
        self.assertTrue(promo.evenements.exists())
        fiche = reverse("agenda:fiche_vitrine", args=[promo.pk])
        self.assertContains(c.get(fiche), "Enregistrer et publier")
        # Référent choisi dans la fiche : publiée en un geste, visible par l'API de la vitrine
        r = c.post(fiche, self.fiche(promo, formateur=self.form_a.pk, places_total=15, action="publier"), follow=True)
        self.assertContains(r, "Annoncée sur le site vitrine")
        promo.refresh_from_db()
        self.assertEqual((promo.statut, promo.publiee_vitrine, promo.etat_session[0]), ("inscriptions", True, "En ligne"))
        code = promo.code_vitrine
        self.assertIn(code, [x["id"] for x in self.client.get("/api/sessions/").json()["sessions"]])
        self.assertTrue(promo.lien_vitrine.endswith(f"/pages/inscription.html?session={code}"))
        liste = c.get(reverse("agenda:promotions"))
        self.assertContains(liste, "Voir sur le site")
        self.assertContains(liste, "Inscriptions")
        # Retrait : brouillon, plus sur le site
        self.assertContains(c.get(fiche), "Retirer du site")
        c.post(fiche, {"action": "retirer"})
        promo.refresh_from_db()
        self.assertEqual((promo.statut, promo.publiee_vitrine), ("planifiee", False))
        self.assertNotIn(code, [x["id"] for x in self.client.get("/api/sessions/").json()["sessions"]])

    def test_creation_directe_publiee_et_complete(self):
        c = self.client_de(self.admin)
        r = c.post(reverse("agenda:session_nouvelle"), {
            "formation": self.formation.pk, "date_debut": (dt.date.today() + dt.timedelta(weeks=3)).isoformat(),
            "nom": "Session express", "formateur": self.form_a.pk, "mode": "Présentiel", "places_total": 1,
            "domaine": "Socle", "code_vitrine": "", "places_hors_plateforme": 1, "effectif_minimum": 1,
            "action": "publier"})
        self.assertRedirects(r, reverse("agenda:promotions"))
        promo = Promotion.objects.get(nom="Session express")
        self.assertEqual((promo.statut, promo.etat_session[0]), ("inscriptions", "Complète"))

    def test_nouvelle_date_de_debut_recale_le_calendrier(self):
        c = self.client_de(self.admin)
        avant = self.promo_a.evenements.order_by("date_debut").first().date_debut
        nouvelle = self.promo_a.date_debut + dt.timedelta(weeks=2)
        c.post(reverse("agenda:fiche_vitrine", args=[self.promo_a.pk]),
               self.fiche(self.promo_a, date_debut=nouvelle.isoformat(), action="enregistrer"))
        apres = self.promo_a.evenements.order_by("date_debut").first().date_debut
        self.assertEqual((apres - avant).days, 14)

    def test_catalogue_session_en_cours(self):
        from apps.agenda.api import fiche_en_cours
        f = self.formation
        f.catalogue = True
        f.save()
        self.promo_a.statut = Promotion.Statut.EN_COURS
        self.promo_a.save()
        self.insc_a.statut = "en_cours"
        self.insc_a.save()
        geoai = next(x for x in self.client.get("/api/catalogue/").json()["formations"] if x["id"] == "geoai-sassandra")
        self.assertEqual(geoai["etat"], "en_cours")
        e = geoai["enCours"]
        premiere = timezone.localdate(self.promo_a.evenements.order_by("date_debut").first().date_debut)
        self.assertEqual((e["dateDebut"], e["apprenants"], e["semaine"]), (premiere.isoformat(), 1, 1))
        self.assertTrue(e["semaines"] > 1 and e["finAffichage"])
        # Semaine courante bornée par la durée de la session
        self.promo_a.nb_apprenants = 1
        tard = fiche_en_cours(self.promo_a, aujourd_hui=premiere + dt.timedelta(weeks=200))
        self.assertEqual((tard["semaine"], tard["progression"]), (tard["semaines"], 100))
        trois = fiche_en_cours(self.promo_a, aujourd_hui=premiere - dt.timedelta(days=premiere.weekday()) + dt.timedelta(weeks=2))
        self.assertEqual(trois["semaine"], 3)

    def test_catalogue_etats_et_ouverture_officielle_par_le_workflow(self):
        from apps.agenda import workflow
        f = self.formation
        f.catalogue, f.resume, f.prix_indicatif = True, "Douze semaines de GéoAI.", "300 000 FCFA"
        f.save()
        def geoai():
            return next(x for x in self.client.get("/api/catalogue/").json()["formations"] if x["id"] == "geoai-sassandra")
        fiches = self.client.get("/api/catalogue/").json()["formations"]
        self.assertEqual(len(fiches), 7)  # les 6 formations reprises du site + GéoAI
        self.assertEqual((geoai()["etat"], geoai()["sessions"], geoai()["prix"]), ("a_venir", [], ""))
        # L'admin ouvre les inscriptions : la session est publiée sans autre geste
        workflow.changer_statut_promotion(self.promo_a, Promotion.Statut.INSCRIPTIONS, self.admin)
        self.promo_a.refresh_from_db()
        self.assertTrue(self.promo_a.publiee_vitrine)
        fiches = self.client.get("/api/catalogue/").json()["formations"]
        self.assertEqual(fiches[0]["id"], "geoai-sassandra")  # les formations ouvertes en tête
        self.assertEqual((fiches[0]["etat"], [s["id"] for s in fiches[0]["sessions"]]), ("ouverte", [self.promo_a.code_vitrine]))
        # Fermeture : retirée du site, la formation reste au catalogue
        workflow.changer_statut_promotion(self.promo_a, Promotion.Statut.PLANIFIEE, self.admin)
        self.assertEqual(geoai()["etat"], "a_venir")
        f.catalogue = False
        f.save()
        self.assertNotIn("geoai-sassandra", [x["id"] for x in self.client.get("/api/catalogue/").json()["formations"]])

    def test_liste_d_interet_puis_annonce_a_l_ouverture(self):
        from django.core import mail
        from apps.agenda import workflow
        from apps.comptes.models import Interet
        self.formation.catalogue = True
        self.formation.save()
        donnees = {"formation": "geoai-sassandra", "nom": "Awa KONÉ", "email": "Awa@Exemple.org", "telephone": "07",
                   "categorie": "etudiant", "structure": "Université FHB"}
        r = self.client.post("/api/interet/", donnees, content_type="application/json", HTTP_ORIGIN="https://www.2kpinnov.org")
        self.assertEqual((r.status_code, r["Access-Control-Allow-Origin"]), (201, "https://www.2kpinnov.org"))
        self.client.post("/api/interet/", {**donnees, "categorie": "professionnel"}, content_type="application/json")
        i = Interet.objects.get()  # même adresse : mise à jour, pas de doublon
        self.assertEqual((i.email, i.categorie, i.structure), ("awa@exemple.org", "professionnel", "Université FHB"))
        self.assertIn("Nous vous préviendrons", mail.outbox[-1].subject)
        self.assertEqual(self.client.post("/api/interet/", {**donnees, "categorie": "?"},
                                          content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post("/api/interet/", {**donnees, "formation": "inconnue"},
                                          content_type="application/json").status_code, 404)
        self.assertIn("1 personne attend une session : Formation GéoAI - Sassandra",
                      [t.titre for t in __import__("apps.tableau_bord.a_faire", fromlist=["x"]).taches_admin(self.admin)])
        message = workflow.changer_statut_promotion(self.promo_a, Promotion.Statut.INSCRIPTIONS, self.admin)
        self.assertIn("1 personne intéressée prévenue", message)
        i.refresh_from_db()
        self.assertEqual(i.promotion_annoncee, self.promo_a)
        self.assertIn(f"inscription.html?session={self.promo_a.code_vitrine}", mail.outbox[-1].body)
        page = self.client_de(self.admin).get(reverse("comptes:candidatures") + "?statut=interets")
        self.assertContains(page, "Awa KONÉ")

    def test_migration_retire_les_sessions_indicatives(self):
        import importlib
        from django.apps import apps as registre
        from apps.formation.models import Formation
        nettoyage = importlib.import_module("apps.agenda.migrations.0012_nettoyage_sessions_indicatives")
        web = Formation.objects.get(slug="websig-cartographie-interactive")  # créée par la migration
        Formation.objects.filter(pk=web.pk).update(catalogue=False, prix_indicatif="")
        indicative = Promotion.objects.create(formation=web, nom="WebSIG", date_debut=dt.date(2026, 10, 8),
                                              statut=Promotion.Statut.INSCRIPTIONS, publiee_vitrine=True,
                                              domaine="Numérique", prix="160 000 FCFA")
        self.promo_a.statut = Promotion.Statut.INSCRIPTIONS  # vraie session (calendrier, apprenant) : conservée
        self.promo_a.save()
        nettoyage.nettoyer(registre, None)
        self.assertFalse(Promotion.objects.filter(pk=indicative.pk).exists())
        self.assertTrue(Promotion.objects.filter(pk=self.promo_a.pk).exists())
        web.refresh_from_db()
        self.assertEqual((web.catalogue, web.domaine, web.prix_indicatif, web.afficher_prix), (True, "Numérique", "160 000 FCFA", False))
        self.assertEqual(Formation.objects.filter(catalogue=True).count(), 6)  # idempotent : pas de doublon


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
        self.assertContains(r, "Publier sur le site")
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
