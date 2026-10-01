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
