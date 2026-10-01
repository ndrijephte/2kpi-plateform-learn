from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from apps.core.models import Parametres
from apps.core.permissions import GROUPE_ADMIN, appliquer_role
from apps.core.test_utils import BaseTest


class RolesEtMenusTests(BaseTest):
    def test_tableau_de_bord_par_role(self):
        attendus = {self.admin: "Pilotage de la plateforme", self.form_a: "Espace formateur",
                    self.app_a: "Progression de la formation"}
        for user, texte in attendus.items():
            self.assertContains(self.client_de(user).get("/"), texte)

    def test_pages_admin_refusees_aux_autres_roles(self):
        for user in (self.form_a, self.app_a):
            c = self.client_de(user)
            for url in ("/comptes/utilisateurs/", "/parametres/identite/", "/parametres/quiz/",
                        "/comptes/candidatures/"):
                self.assertEqual(c.get(url).status_code, 403, (user, url))

    def test_groupe_admin_synchronise_avec_le_role(self):
        self.assertTrue(self.admin.groups.filter(name=GROUPE_ADMIN).exists())
        self.assertTrue(self.admin.is_staff)
        self.assertEqual(self.client_de(self.admin).get("/admin/evaluation/quiz/").status_code, 200)
        appliquer_role(self.admin, "formateur")
        self.assertFalse(self.admin.groups.filter(name=GROUPE_ADMIN).exists())
        self.assertFalse(self.admin.is_staff)
        self.assertTrue(Group.objects.filter(name=GROUPE_ADMIN).exists())


class ParametresTests(BaseTest):
    def test_identite_et_logo(self):
        c = self.client_de(self.admin)
        r = c.post("/parametres/identite/", {"nom_plateforme": "Acme", "suffixe": "Academy", "slogan": "x",
                                             "logo": SimpleUploadedFile("logo.png", b"\x89PNG", "image/png")})
        self.assertEqual(r.status_code, 302)
        self.assertContains(self.client_de(self.app_a).get("/"), "Acme <em>Academy</em>")
        logo = Parametres.charger().logo.name
        self.assertEqual(self.client.get(f"/media/{logo}").status_code, 200)

    def test_media_publique_liste_blanche(self):
        for url in ("/media/ressources/x.pdf", "/media/livrables/x.pdf", "/media/prive/x"):
            self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get("/media/parametres/../../.env").status_code, 400)

    def test_fil_ariane_seance(self):
        s = self.m1.seances.first()
        r = self.client_de(self.admin).get(reverse("core:modifier", args=["seance", s.pk]))
        for lien in (reverse("core:parametres"), reverse("core:formations"),
                     reverse("core:formation", args=[self.formation.pk]), reverse("core:module", args=[self.m1.pk])):
            self.assertContains(r, f'href="{lien}"')

    def test_suppression_protegee(self):
        c = self.client_de(self.admin)
        c.post(reverse("core:supprimer", args=["formation", self.formation.pk]))
        self.assertTrue(type(self.formation).objects.filter(pk=self.formation.pk).exists())

    def test_quiz_question_et_import_gift(self):
        c = self.client_de(self.admin)
        c.post("/parametres/quiz/", {"module": self.m2.pk, "titre": "Test S2", "bareme": 20})
        quiz = self.m2.quiz.get(titre="Test S2")
        base = {"choix-TOTAL_FORMS": "4", "choix-INITIAL_FORMS": "0", "choix-MIN_NUM_FORMS": "0",
                "choix-MAX_NUM_FORMS": "1000"}
        url = reverse("core:question_ajouter", args=[quiz.pk])
        r = c.post(url, {**base, "intitule": "Q", "type": "qcm", "choix-0-texte": "A", "choix-1-texte": "B"})
        self.assertContains(r, "au moins une réponse correcte")
        r = c.post(url, {**base, "intitule": "Q", "type": "qcm", "choix-0-texte": "A", "choix-0-correct": "on",
                         "choix-1-texte": "B"})
        self.assertEqual(r.status_code, 302)
        gift = SimpleUploadedFile("q.gift", "::Q:: La Terre est ronde {T}\n".encode(), "text/plain")
        c.post(reverse("core:quiz", args=[quiz.pk]), {"quoi": "gift", "fichier": gift})
        self.assertEqual(quiz.questions.count(), 2)
