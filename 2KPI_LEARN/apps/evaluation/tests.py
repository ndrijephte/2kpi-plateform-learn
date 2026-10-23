from django.core.files.base import ContentFile
from django.urls import reverse
from apps.agenda.models import AccesModule
from apps.core.test_utils import BaseTest
from apps.evaluation.models import Inscription, Livrable, Quiz, TentativeQuiz


class QuizTests(BaseTest):
    def setUp(self):
        super().setUp()
        self.quiz = Quiz.objects.get(module=self.m1)
        self.url = reverse("evaluation:quiz", args=[self.quiz.pk])

    def test_seul_l_apprenant_inscrit_passe_le_quiz(self):
        self.assertEqual(self.client_de(self.app_a).get(self.url).status_code, 200)
        for user in (self.form_a, self.admin):
            self.assertEqual(self.client_de(user).post(self.url, {}).status_code, 403)
        self.assertEqual(self.client_de(self.app_b).get(self.url).status_code, 403)  # module fermé (promo B)
        self.assertFalse(TentativeQuiz.objects.exclude(inscription=self.insc_a).exists())

    def test_correction_parfaite(self):
        data = {}
        for q in self.quiz.questions.prefetch_related("choix"):
            if q.type in ("qcm", "vf"):
                data[f"q{q.id}"] = [str(c.id) for c in q.choix.all() if c.correct]
            elif q.type == "court":
                data[f"q{q.id}"] = q.reponse_courte.split("|")[0].strip()
            elif q.type == "num":
                data[f"q{q.id}"] = q.reponse_courte.split(":")[0]
            else:
                for c in q.choix.all():
                    data[f"q{q.id}_{c.id}"] = c.texte.split("->")[1].strip()
        self.client_de(self.app_a).post(self.url, data)
        self.assertEqual(TentativeQuiz.objects.get(inscription=self.insc_a).score, 20)

    def test_resultats_pour_le_formateur(self):
        url = reverse("evaluation:quiz_resultats", args=[self.quiz.pk])
        r = self.client_de(self.form_a).get(url)
        self.assertContains(r, "App_a")
        self.assertNotContains(r, "App_b")
        self.assertEqual(self.client_de(self.app_a).get(url).status_code, 403)


class LivrablesTests(BaseTest):
    def setUp(self):
        super().setUp()
        self.livrable = Livrable.objects.create(inscription=self.insc_a, seance=self.m1.seances.first(), rendu=True)
        self.livrable.fichier.save("l.pdf", ContentFile(b"LIVRABLE"))

    def test_fichier_du_livrable(self):
        url = reverse("evaluation:livrable_fichier", args=[self.livrable.pk])
        for user, code in ((self.app_a, 200), (self.form_a, 200), (self.admin, 200),
                           (self.app_b, 403), (self.form_b, 403)):
            self.assertEqual(self.client_de(user).get(url).status_code, code, user)

    def test_correction_et_notification(self):
        c = self.client_de(self.form_a)
        c.post("/evaluation/livrables/", {"livrable": self.livrable.pk, "note": "25"})
        self.livrable.refresh_from_db()
        self.assertIsNone(self.livrable.note_sur_20)
        c.post("/evaluation/livrables/", {"livrable": self.livrable.pk, "note": "14,5", "observations": "Bien"})
        self.livrable.refresh_from_db()
        self.assertEqual(float(self.livrable.note_sur_20), 14.5)
        self.assertTrue(self.app_a.notifications.filter(titre__startswith="Livrable corrigé",
                                                        expediteur=self.form_a).exists())
        self.assertEqual(self.client_de(self.form_b).post("/evaluation/livrables/",
                                                          {"livrable": self.livrable.pk, "note": "1"}).status_code, 404)


class AutoEvaluationTests(BaseTest):
    """Auto-évaluation des apprenants sur les objectifs des séances."""

    def setUp(self):
        super().setUp()
        from apps.formation.models import definir_objectifs
        self.seance = self.m1.seances.order_by("ordre").first()
        definir_objectifs(self.seance, ["Créer un compte Earth Engine", "Charger une image Sentinel-2"])
        self.o1, self.o2 = self.seance.objectifs_seance.order_by("ordre")
        self.url = reverse("formation:seance", args=[self.seance.pk])

    def test_apprenant_s_evalue_et_progresse(self):
        from apps.evaluation.models import AutoEvaluation
        c = self.client_de(self.app_a)
        self.assertContains(c.get(self.url), "Mon auto-évaluation")
        c.post(self.url, {"action": "autoevaluation", f"niveau_{self.o1.pk}": "1"})
        a = AutoEvaluation.objects.get(objectif=self.o1)
        self.assertEqual((a.niveau, a.niveau_initial), (1, 1))
        self.assertFalse(AutoEvaluation.objects.filter(objectif=self.o2).exists())  # réponse partielle
        c.post(self.url, {"action": "autoevaluation", f"niveau_{self.o1.pk}": "3", f"niveau_{self.o2.pk}": "9"})
        a.refresh_from_db()
        self.assertEqual((a.niveau, a.niveau_initial, a.progression, a.acquis), (3, 1, 2, True))
        self.assertFalse(AutoEvaluation.objects.filter(objectif=self.o2).exists())  # niveau invalide ignoré
        self.assertFalse(Livrable.objects.exists())  # n'est pas pris pour un dépôt de livrable
        acquis = c.get(reverse("evaluation:mes_acquis"))
        self.assertEqual(acquis.context["synthese"]["acquis"], 1)
        self.assertContains(acquis, "Créer un compte Earth Engine")

    def test_module_ferme_ou_autre_role(self):
        from apps.evaluation.models import AutoEvaluation
        self.client_de(self.app_b).post(self.url, {"action": "autoevaluation", f"niveau_{self.o1.pk}": "2"})
        r = self.client_de(self.form_a).post(self.url, {"action": "autoevaluation", f"niveau_{self.o1.pk}": "2"})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(AutoEvaluation.objects.exists())

    def test_demande_d_aide_notifiee_et_traitee(self):
        from apps.evaluation.models import AutoEvaluation
        self.client_de(self.app_a).post(self.url, {"action": "autoevaluation", f"niveau_{self.o2.pk}": "1",
                                                   f"aide_{self.o2.pk}": "on", f"commentaire_{self.o2.pk}": "Erreur d'authentification"})
        self.assertTrue(self.form_a.notifications.filter(titre__startswith="Demande d'aide").exists())
        self.assertFalse(self.form_b.notifications.filter(titre__startswith="Demande d'aide").exists())
        url = reverse("evaluation:autoevaluations", args=[self.promo_a.pk])
        r = self.client_de(self.form_a).get(url + "?filtre=aide")
        self.assertContains(r, "Erreur d&#x27;authentification")
        self.assertContains(self.client_de(self.form_a).get("/"), "Demandes d'aide")
        a = AutoEvaluation.objects.get()
        self.client_de(self.form_a).post(url, {"autoevaluation": a.pk})
        a.refresh_from_db()
        self.assertFalse(a.besoin_aide)
        self.assertTrue(self.app_a.notifications.filter(titre__icontains="demande d'aide").exists())

    def test_synthese_reservee_aux_formateurs_de_la_promotion(self):
        url = reverse("evaluation:autoevaluations", args=[self.promo_a.pk])
        self.assertEqual(self.client_de(self.form_b).get(url).status_code, 404)
        self.assertEqual(self.client_de(self.app_a).get(url).status_code, 403)
        self.assertEqual(self.client_de(self.admin).get(url).status_code, 200)

    def test_objectifs_reformules_sans_perte(self):
        from apps.evaluation.models import AutoEvaluation
        from apps.formation.models import definir_objectifs
        AutoEvaluation.objects.create(inscription=self.insc_a, objectif=self.o1, niveau=2, niveau_initial=2)
        definir_objectifs(self.seance, ["Charger une image Sentinel-2", "Créer et activer un compte Earth Engine"])
        self.o2.refresh_from_db()
        self.assertEqual(self.o2.ordre, 1)                    # inchangé, simplement déplacé
        self.o1.refresh_from_db()
        self.assertEqual(self.o1.libelle, "Créer et activer un compte Earth Engine")  # reformulé, réponses gardées
        definir_objectifs(self.seance, ["Charger une image Sentinel-2", "Exporter un NDVI vers Drive"])
        self.o1.refresh_from_db()
        self.assertFalse(self.o1.actif)                       # archivé : il a des réponses
        self.assertEqual(AutoEvaluation.objects.count(), 1)
        self.assertTrue(self.seance.objectifs_seance.filter(libelle="Exporter un NDVI vers Drive", actif=True).exists())
        definir_objectifs(self.seance, ["Créer et activer un compte Earth Engine"])  # réactivé à l'identique
        self.o1.refresh_from_db()
        self.assertTrue(self.o1.actif)

    def test_objectifs_ligne_par_ligne_publies_aux_apprenants(self):
        seance = self.m1.seances.order_by("ordre")[1]
        url = reverse("formation:seance", args=[seance.pk])
        self.assertContains(self.client_de(self.app_a).get(url), "Objectifs pas encore publiés")
        r = self.client_de(self.form_a).get(url)
        self.assertContains(r, "data-objectifs")
        self.assertContains(r, "Enregistrer et publier")
        donnees = {"action": "objectifs", "objectifs_liste": ["Lire un raster", "", "Calculer un NDVI"]}
        r = self.client_de(self.form_a).post(url, donnees)
        self.assertRedirects(r, url + "#objectifs", fetch_redirect_response=False)
        self.assertEqual(list(seance.objectifs_seance.values_list("libelle", flat=True)),
                         ["Lire un raster", "Calculer un NDVI"])
        notif = self.app_a.notifications.filter(titre__contains="à auto-évaluer")
        self.assertEqual(notif.count(), 1)                    # M1 ouvert pour la promotion A
        self.assertFalse(self.app_b.notifications.filter(titre__contains="à auto-évaluer").exists())
        self.client_de(self.form_a).post(url, donnees)       # rien de nouveau : pas de 2e notification
        self.assertEqual(notif.count(), 1)
        r = self.client_de(self.app_a).get(url)
        self.assertContains(r, "Mon auto-évaluation")
        self.assertContains(r, "Calculer un NDVI")
        self.assertEqual(self.client_de(self.app_a).post(url, donnees).status_code, 403)
        self.assertFalse(Livrable.objects.exists())

    def test_formateur_redige_les_objectifs(self):
        url = reverse("formation:objectifs", args=[self.seance.pk])
        sans_acces = self.compte("form_c", "formateur")  # aucune promotion confiée
        self.assertEqual(self.client_de(sans_acces).get(url).status_code, 404)
        r = self.client_de(self.form_a).post(url, {"objectifs_liste": "- Objectif A\n\n• Objectif B\nObjectif A"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(list(self.seance.objectifs_seance.filter(actif=True).values_list("libelle", flat=True)),
                         ["Objectif A", "Objectif B"])
        r = self.client_de(self.form_a).post(url, {"objectifs_liste": "\n".join(f"O{i}" for i in range(13))})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "12 objectifs au maximum")


class GrilleEtPrerequisTests(BaseTest):
    """Prérequis et grille d'évaluation définis par formation, saisis par promotion."""

    def setUp(self):
        super().setUp()
        from apps.agenda.models import Promotion
        self.promo_a.statut = Promotion.Statut.EN_COURS
        self.promo_a.save()
        self.url = reverse("evaluation:evaluation_promotion", args=[self.promo_a.pk])

    def test_seed_geoai_et_note_identique_a_l_ancienne_formule(self):
        from decimal import Decimal
        from apps.evaluation import grille
        from apps.evaluation.models import Soutenance
        self.assertEqual(self.formation.prerequis.count(), 6)
        self.assertEqual(sum(c.poids for c in self.formation.criteres.all()), 100)
        # Projet : 20 % × 20 + 80 % × 10 = 12 ; finale = 0,4 × 0 + 0,4 × 12 + 0,2 × 15 = 7,8
        criteres = list(self.formation.criteres.all())
        acquisition = next(c for c in criteres if c.libelle.startswith("Acquisition"))
        grille.enregistrer_notes(self.insc_a, {c.pk: Decimal(20 if c == acquisition else 10) for c in criteres})
        Soutenance.objects.create(inscription=self.insc_a, note_sur_20=15)
        self.assertEqual(grille.note_projet(self.insc_a), Decimal("12.00"))
        from apps.tableau_bord.services import synthese
        self.assertEqual(synthese(self.insc_a)["note_globale"], 7.8)

    def test_formation_sans_grille_ni_soutenance(self):
        from decimal import Decimal
        from apps.evaluation import grille
        from apps.formation.models import Formation
        f = Formation.objects.create(titre="Kobo", poids_continu=100, poids_projet=0, poids_soutenance=0)
        self.assertEqual(grille.note_finale(f, 14.5, None, None), Decimal("14.50"))
        f2 = Formation.objects.create(titre="WebSIG")  # 40/40/20 mais sans critère : continu 2/3, soutenance 1/3
        self.assertEqual(grille.note_finale(f2, 12, None, 15), Decimal("13.00"))

    def test_saisie_par_le_referent_et_consultation_des_autres(self):
        criteres = list(self.formation.criteres.all())
        donnees = {"quoi": "notes", f"s_{self.insc_a.pk}": "14,5",
                   **{f"n_{self.insc_a.pk}_{c.pk}": "12" for c in criteres}}
        r = self.client_de(self.form_a).post(self.url, {**donnees, f"n_{self.insc_a.pk}_{criteres[0].pk}": "25"}, follow=True)
        self.assertContains(r, "Rien n&#x27;a été enregistré")
        self.assertFalse(self.insc_a.notes_criteres.exists())
        self.client_de(self.form_a).post(self.url, donnees)
        self.assertEqual(self.insc_a.notes_criteres.count(), len(criteres))
        self.assertEqual(str(self.insc_a.soutenance.note_sur_20), "14.5")
        page = self.client_de(self.form_a).get(self.url)
        self.assertEqual(page.context["lignes_notes"][0]["manques"], [])
        # Formateur affecté (non référent) : consultation seulement
        from apps.agenda.models import Affectation
        Affectation.objects.create(promotion=self.promo_a, formateur=self.form_b, tous_les_modules=True)
        self.assertFalse(self.client_de(self.form_b).get(self.url).context["peut_saisir"])
        self.assertEqual(self.client_de(self.form_b).post(self.url, donnees).status_code, 403)
        self.assertEqual(self.client_de(self.app_a).get(self.url).status_code, 403)

    def test_prerequis_obligatoire_bloque_la_confirmation(self):
        from apps.agenda import workflow
        from apps.agenda.models import Promotion
        from apps.evaluation import grille
        p = self.formation.prerequis.first()
        p.obligatoire = True
        p.save()
        self.promo_b.statut = Promotion.Statut.INSCRIPTIONS
        self.promo_b.save()
        insc = Inscription.objects.create(apprenant=self.compte("app_y", "apprenant"), formation=self.formation,
                                          promotion=self.promo_b, paiement=Inscription.Paiement.RECU)
        with self.assertRaises(workflow.TransitionRefusee) as refus:
            workflow.changer_statut_inscription(insc, Inscription.Statut.CONFIRMEE, self.admin)
        self.assertIn(p.libelle, refus.exception.manques[0])
        # L'apprenant le coche depuis son profil, puis la confirmation passe
        c = self.client_de(insc.apprenant)
        c.post(reverse("comptes:profil_modifier"), {"c-first_name": "Y", "c-last_name": "Z", "c-email": "app_y@exemple.org",
                                                     f"r-p{p.pk}": grille.OK})
        self.assertEqual(grille.obligatoires_manquants(insc), [])
        workflow.changer_statut_inscription(insc, Inscription.Statut.CONFIRMEE, self.admin)

    def test_parametres_poids_et_grille_totalisent_100(self):
        url = reverse("core:formation", args=[self.formation.pk])
        c = self.client_de(self.admin)
        r = c.post(url, {"quoi": "formation", "titre": self.formation.titre, "slug": self.formation.slug, "active": "on",
                         "seuil_assiduite": 80, "note_minimale": 10, "poids_continu": 50, "poids_projet": 40,
                         "poids_soutenance": 20})
        self.assertContains(r, "totaliser 100 %")
        criteres = list(self.formation.criteres.all())
        base = {"quoi": "criteres", "cr-TOTAL_FORMS": len(criteres) + 3, "cr-INITIAL_FORMS": len(criteres),
                "cr-MIN_NUM_FORMS": 0, "cr-MAX_NUM_FORMS": 1000}
        for n, cr in enumerate(criteres):
            base.update({f"cr-{n}-id": cr.pk, f"cr-{n}-libelle": cr.libelle, f"cr-{n}-poids": cr.poids, f"cr-{n}-ordre": cr.ordre})
        base.update({f"cr-{n}-ordre": 0 for n in range(len(criteres), len(criteres) + 3)})  # lignes vides du navigateur
        self.assertContains(c.post(url, {**base, "cr-0-poids": 30}), "totaliser 100 %")
        r = c.post(url, {**base, "cr-0-poids": 10, f"cr-{len(criteres)}-libelle": "Oral", f"cr-{len(criteres)}-poids": 10})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.formation.criteres.count(), len(criteres) + 1)
