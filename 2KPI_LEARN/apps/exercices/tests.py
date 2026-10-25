import datetime as dt
from decimal import Decimal
from django.urls import reverse
from django.utils import timezone
from apps.core.test_utils import BaseTest
from .models import Choix, Copie, Exercice, Planification, Question

T = Question.Type


class ExercicesTests(BaseTest):
    """Le formateur compose (barème, correction) et planifie ; l'apprenant s'exerce dans le délai,
    puis voit son résultat et la correction."""

    def setUp(self):
        super().setUp()
        self.ex = Exercice.objects.create(module=self.m1, titre="Indices spectraux", auteur=self.form_a)
        self.qcm = Question.objects.create(exercice=self.ex, type=T.QCM, enonce="Bandes du NDVI ?", points=2, ordre=1,
                                           correction="Rouge et proche infrarouge.")
        self.rouge = Choix.objects.create(question=self.qcm, texte="Rouge", correct=True)
        self.pir = Choix.objects.create(question=self.qcm, texte="PIR", correct=True)
        self.bleu = Choix.objects.create(question=self.qcm, texte="Bleu")
        self.courte = Question.objects.create(exercice=self.ex, type=T.COURTE, enonce="Indice d'eau ?", points=1,
                                              ordre=2, reponses_acceptees="NDWI|indice d'eau")
        self.num = Question.objects.create(exercice=self.ex, type=T.NUMERIQUE, enonce="NDVI max ?", points=1, ordre=3,
                                           valeur_attendue=Decimal(1), tolerance=Decimal("0.05"))
        self.redac = Question.objects.create(exercice=self.ex, type=T.REDACTION, enonce="Expliquez.", points=4, ordre=4)
        maintenant = timezone.now()
        self.planif = Planification.objects.create(exercice=self.ex, promotion=self.promo_a,
                                                   ouverture=maintenant - dt.timedelta(hours=1),
                                                   date_limite=maintenant + dt.timedelta(days=2))

    def repondre(self, **extra):
        donnees = {f"q{self.qcm.pk}": [self.rouge.pk, self.pir.pk], f"q{self.courte.pk}": "  ndwi ",
                   f"q{self.num.pk}": "0,97", f"q{self.redac.pk}": "Parce que la chlorophylle…", **extra}
        return self.client_de(self.app_a).post(reverse("exercices:faire", args=[self.planif.pk]), donnees)

    def test_composition_par_le_formateur_du_module(self):
        c = self.client_de(self.form_a)
        r = c.post(reverse("exercices:liste"), {"module": self.m1.pk, "titre": "Quiz QGIS", "consignes": ""})
        ex = Exercice.objects.get(titre="Quiz QGIS")
        self.assertRedirects(r, reverse("exercices:exercice", args=[ex.pk]))
        url = reverse("exercices:question_ajouter", args=[ex.pk])
        gestion = {"choix-TOTAL_FORMS": 4, "choix-INITIAL_FORMS": 0, "choix-MIN_NUM_FORMS": 0, "choix-MAX_NUM_FORMS": 1000}
        c.post(url, {**gestion, "type": "vf", "enonce": "QGIS est libre.", "points": "1", "ordre": 1,
                     "bonne_reponse_vf": "vrai", "tolerance": "0"})
        q = ex.questions.get()
        self.assertEqual(list(q.choix.values_list("texte", "correct")), [("Vrai", True), ("Faux", False)])
        r = c.post(url, {**gestion, "type": "qcm", "enonce": "?", "points": "1", "ordre": 2, "tolerance": "0",
                         "choix-0-texte": "Une seule"})
        self.assertContains(r, "au moins deux propositions")
        # Hors de son périmètre : pas d'accès
        self.assertEqual(self.client_de(self.form_b).get(reverse("exercices:exercice", args=[ex.pk])).status_code, 200)  # form_b est référent de B (même formation)
        autre = self.compte("form_c", "formateur")
        self.assertEqual(self.client_de(autre).get(reverse("exercices:exercice", args=[ex.pk])).status_code, 404)

    def test_qcm_propositions_ajoutees_et_retirees(self):
        c = self.client_de(self.form_a)
        url = reverse("exercices:question_ajouter", args=[self.ex.pk])
        r = c.get(url)
        self.assertEqual(r.context["formset"].total_form_count(), 2)  # deux lignes pour commencer
        self.assertContains(r, "Ajouter une proposition")
        textes = ["A", "B", "C", "D", "E", "F"]
        donnees = {"choix-TOTAL_FORMS": 6, "choix-INITIAL_FORMS": 0, "choix-MIN_NUM_FORMS": 0,
                   "choix-MAX_NUM_FORMS": 1000, "type": "qcm", "enonce": "Six choix ?", "points": "1",
                   "ordre": 5, "tolerance": "0", "choix-5-correct": "on", "choix-4-DELETE": "on"}
        donnees.update({f"choix-{i}-texte": t for i, t in enumerate(textes)})
        c.post(url, donnees)
        q = self.ex.questions.get(enonce="Six choix ?")
        self.assertEqual(list(q.choix.values_list("texte", "correct", "ordre")),
                         [("A", False, 1), ("B", False, 2), ("C", False, 3), ("D", False, 4), ("F", True, 5)])
        # Modification : on retire « A » et on ajoute « G » (bonne réponse)
        r = c.get(reverse("exercices:question", args=[self.ex.pk, q.pk]))
        self.assertEqual(r.context["formset"].total_form_count(), 5)  # pas de lignes vides en trop
        choix = list(q.choix.all())
        modif = {"choix-TOTAL_FORMS": 6, "choix-INITIAL_FORMS": 5, "choix-MIN_NUM_FORMS": 0, "choix-MAX_NUM_FORMS": 1000,
                 "type": "qcm", "enonce": "Six choix ?", "points": "1", "ordre": 5, "tolerance": "0",
                 "choix-0-DELETE": "on", "choix-5-texte": "G", "choix-5-correct": "on"}
        for i, ch in enumerate(choix):
            modif.update({f"choix-{i}-id": ch.pk, f"choix-{i}-texte": ch.texte})
            if ch.correct:
                modif[f"choix-{i}-correct"] = "on"
        c.post(reverse("exercices:question", args=[self.ex.pk, q.pk]), modif)
        self.assertEqual(list(q.choix.values_list("texte", "correct")),
                         [("B", False), ("C", False), ("D", False), ("F", True), ("G", True)])

    def test_consignes_mises_en_forme(self):
        self.ex.consignes = "<p>Lis <strong>tout</strong></p><ol><li>Calcule</li></ol><script>alert(1)</script>"
        self.ex.save()
        r = self.client_de(self.app_a).get(reverse("exercices:faire", args=[self.planif.pk]))
        self.assertContains(r, "<p>Lis <strong>tout</strong></p><ol><li>Calcule</li></ol>")
        self.assertNotContains(r, "alert(1)")
        c = self.client_de(self.form_a)
        c.post(reverse("exercices:exercice", args=[self.ex.pk]), {
            "quoi": "exercice", "module": self.m1.pk, "titre": self.ex.titre,
            "consignes": '<p onclick="x()"><em>Avant</em> lundi</p>'})
        self.ex.refresh_from_db()
        self.assertEqual(self.ex.consignes, "<p><em>Avant</em> lundi</p>")

    def test_enonce_et_correction_mis_en_forme(self):
        c = self.client_de(self.form_a)
        url = reverse("exercices:question_ajouter", args=[self.ex.pk])
        gestion = {"choix-TOTAL_FORMS": 0, "choix-INITIAL_FORMS": 0, "choix-MIN_NUM_FORMS": 0, "choix-MAX_NUM_FORMS": 1000}
        c.post(url, {**gestion, "type": "redaction", "points": "2", "ordre": 9, "tolerance": "0",
                     "enonce": "<p>Explique le <b>NDVI</b></p><ul><li>formule</li><li>usage</li></ul>",
                     "correction": '<p><i>NDVI</i> = (PIR - R) / (PIR + R)</p><img src=x onerror="alert(1)">'})
        q = self.ex.questions.get(ordre=9)
        self.assertEqual(q.enonce, "<p>Explique le <b>NDVI</b></p><ul><li>formule</li><li>usage</li></ul>")
        self.assertEqual(q.correction, "<p><i>NDVI</i> = (PIR - R) / (PIR + R)</p>")
        self.assertEqual(str(q), "Explique le NDVI\n- formule\n- usage")
        r = self.client_de(self.app_a).get(reverse("exercices:faire", args=[self.planif.pk]))
        self.assertContains(r, "<p>Explique le <b>NDVI</b></p><ul><li>formule</li><li>usage</li></ul>")
        r = c.post(url, {**gestion, "type": "redaction", "points": "1", "ordre": 10, "tolerance": "0",
                         "enonce": "<p><br></p>"})
        self.assertFalse(self.ex.questions.filter(ordre=10).exists())  # énoncé vide refusé

    def test_planification_previent_les_apprenants(self):
        c = self.client_de(self.form_a)
        ex = Exercice.objects.create(module=self.m1, titre="Bis")
        Question.objects.create(exercice=ex, type=T.REDACTION, enonce="?", points=1)
        r = c.post(reverse("exercices:exercice", args=[ex.pk]), {
            "quoi": "planifier", "promotion": self.promo_a.pk,
            "ouverture": "2026-11-02T08:00", "date_limite": "2026-11-01T08:00"})
        self.assertContains(r, "La date limite doit suivre")
        c.post(reverse("exercices:exercice", args=[ex.pk]), {
            "quoi": "planifier", "promotion": self.promo_a.pk, "ouverture": "2026-11-02T08:00", "date_limite": "2026-11-09T18:00"})
        self.assertTrue(Planification.objects.filter(exercice=ex, promotion=self.promo_a).exists())
        n = self.app_a.notifications.get(titre="Nouvel exercice : Bis")
        planif = Planification.objects.get(exercice=ex, promotion=self.promo_a)
        self.assertEqual((n.module, n.destination), (self.m1, reverse("exercices:faire", args=[planif.pk])))
        self.assertFalse(self.app_b.notifications.filter(titre="Nouvel exercice : Bis").exists())
        # promo_b n'est pas proposée à form_a
        r = c.post(reverse("exercices:exercice", args=[ex.pk]), {
            "quoi": "planifier", "promotion": self.promo_b.pk, "ouverture": "2026-11-02T08:00", "date_limite": "2026-11-09T18:00"})
        self.assertFalse(Planification.objects.filter(exercice=ex, promotion=self.promo_b).exists())

    def test_cycle_apprenant_notation_et_resultat_apres_la_date_limite(self):
        from apps.tableau_bord.a_faire import taches_apprenant, taches_formateur
        self.assertIn("Exercice à faire : Indices spectraux", [t.titre for t in taches_apprenant(self.app_a, self.insc_a)])
        self.repondre()
        copie = Copie.objects.get(planification=self.planif, inscription=self.insc_a)
        points = {r.question_id: r.points for r in copie.reponses.all()}
        self.assertEqual(points, {self.qcm.pk: 2, self.courte.pk: 1, self.num.pk: 1, self.redac.pk: None})
        # Modifiable jusqu'à la date limite ; ni note ni correction avant
        self.repondre(**{f"q{self.qcm.pk}": [self.rouge.pk]})
        self.assertEqual(copie.reponses.get(question=self.qcm).points, 0)
        r = self.client_de(self.app_a).get(reverse("exercices:resultat", args=[self.planif.pk]))
        self.assertRedirects(r, reverse("exercices:faire", args=[self.planif.pk]))
        self.assertNotContains(self.client_de(self.app_a).get(reverse("exercices:faire", args=[self.planif.pk])), "Rouge et proche infrarouge")
        # L'exercice est figé dès la première réponse
        self.assertTrue(self.ex.verrouille)
        r = self.client_de(self.form_a).post(reverse("exercices:question_supprimer", args=[self.ex.pk, self.qcm.pk]))
        self.assertTrue(Question.objects.filter(pk=self.qcm.pk).exists())
        # Date limite passée : plus de modification, correction en cours (réponse rédigée)
        self.planif.date_limite = timezone.now() - dt.timedelta(minutes=1)
        self.planif.save()
        self.repondre()
        self.assertEqual(copie.reponses.get(question=self.qcm).points, 0)
        page = self.client_de(self.app_a).get(reverse("exercices:resultat", args=[self.planif.pk]))
        self.assertContains(page, "Correction en cours")
        self.assertIn("Indices spectraux : 1 copie à corriger", [t.titre for t in taches_formateur(self.form_a)])
        # Le formateur note la réponse rédigée : résultat visible et apprenant prévenu
        url = reverse("exercices:corriger", args=[copie.pk])
        self.client_de(self.form_a).post(url, {f"points_{self.redac.pk}": "9"})
        self.assertIsNone(copie.reponses.get(question=self.redac).points)  # 9 > 4 refusé
        self.client_de(self.form_a).post(url, {f"points_{self.redac.pk}": "3,5", f"commentaire_{self.redac.pk}": "Bien"})
        self.assertTrue(self.app_a.notifications.filter(titre="Résultat disponible : Indices spectraux").exists())
        page = self.client_de(self.app_a).get(reverse("exercices:resultat", args=[self.planif.pk]))
        # 0 + 1 + 1 + 3,5 = 5,5 / 8 → 13,75/20
        self.assertEqual(page.context["resultat"]["note_sur_20"], Decimal("13.75"))
        self.assertContains(page, "Rouge et proche infrarouge")
        self.assertContains(page, "Bien")

    def test_apprenant_d_une_autre_promotion_et_exercice_a_venir(self):
        self.assertEqual(self.client_de(self.app_b).get(reverse("exercices:faire", args=[self.planif.pk])).status_code, 404)
        self.planif.ouverture = timezone.now() + dt.timedelta(days=1)
        self.planif.save()
        r = self.client_de(self.app_a).get(reverse("exercices:faire", args=[self.planif.pk]))
        self.assertContains(r, "Cet exercice ouvre le")
        self.assertNotContains(r, "Bandes du NDVI")
        self.repondre()
        self.assertFalse(Copie.objects.exists())

    def test_resultats_automatiques_annonces_par_la_tache_quotidienne(self):
        from apps.exercices.services import notifier_resultats_du_jour
        self.redac.delete()
        self.repondre()
        self.planif.date_limite = timezone.now() - dt.timedelta(minutes=1)
        self.planif.save()
        self.assertEqual(notifier_resultats_du_jour(), 1)
        self.assertEqual(notifier_resultats_du_jour(), 0)  # une seule fois
