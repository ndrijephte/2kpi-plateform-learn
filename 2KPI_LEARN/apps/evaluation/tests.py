from django.core.files.base import ContentFile
from django.urls import reverse
from apps.agenda.models import AccesModule
from apps.core.test_utils import BaseTest
from apps.evaluation.models import Livrable, Quiz, TentativeQuiz


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
