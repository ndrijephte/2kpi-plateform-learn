from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from apps.agenda.models import AccesModule
from apps.core.test_utils import BaseTest
from apps.formation.models import Ressource


class AccesContenusTests(BaseTest):
    def test_module_ouvert_et_ferme(self):
        c = self.client_de(self.app_a)
        self.assertEqual(c.get("/formation/modules/M1/").status_code, 200)
        r = c.get("/formation/modules/M2/")
        self.assertEqual(r.status_code, 403)
        self.assertContains(r, "pas encore accessible", status_code=403)
        self.assertEqual(c.get(reverse("formation:seance", args=[self.m2.seances.first().pk])).status_code, 403)

    def test_ouverture_propre_a_la_promotion(self):
        self.assertEqual(self.client_de(self.app_b).get("/formation/modules/M1/").status_code, 403)

    def test_inscription_inactive(self):
        self.insc_a.statut = "terminee"
        self.insc_a.save()
        self.assertContains(self.client_de(self.app_a).get("/formation/modules/M1/"), "pas active", status_code=403)

    def test_formateur_gere_l_acces_de_ses_promotions(self):
        url = reverse("agenda:acces", args=[self.promo_a.pk])
        self.assertEqual(self.client_de(self.form_b).get(url).status_code, 404)
        c = self.client_de(self.form_a)
        c.post(url, {"module": self.m2.pk, "etat": "ouvert", "prevenir": "on"})
        self.assertEqual(AccesModule.objects.get(promotion=self.promo_a, module=self.m2).etat, "ouvert")
        self.assertTrue(self.app_a.notifications.filter(titre__contains="M2").exists())
        self.assertEqual(self.client_de(self.app_a).get("/formation/modules/M2/").status_code, 200)

    def test_staff_toujours_acces(self):
        self.assertEqual(self.client_de(self.form_b).get("/formation/modules/M2/").status_code, 200)


class RessourcesTests(BaseTest):
    def test_depot_formats(self):
        c = self.client_de(self.form_a)
        s = self.m1.seances.first()
        for nom in ("cours.pdf", "tp.ipynb", "donnees.zip", "couche.gpkg"):
            r = c.post("/formation/ressources/ajouter/", {"titre": nom, "seance": s.pk,
                                                         "fichier": SimpleUploadedFile(nom, b"x")})
            self.assertEqual(r.status_code, 302, nom)
        self.assertEqual(sorted(Ressource.objects.values_list("type", flat=True)),
                         ["archive", "donnees", "notebook", "pdf"])
        for nom in ("page.html", "script.exe", "image.svg"):
            r = c.post("/formation/ressources/ajouter/", {"titre": nom, "seance": s.pk,
                                                         "fichier": SimpleUploadedFile(nom, b"x")})
            self.assertContains(r, "non autorisé")

    def test_telechargement_controle(self):
        r1 = Ressource.objects.create(seance=self.m1.seances.first(), titre="R1", type="pdf")
        r1.fichier.save("r1.pdf", ContentFile(b"CONTENU-M1"))
        r2 = Ressource.objects.create(module=self.m2, titre="R2", type="pdf")
        r2.fichier.save("r2.pdf", ContentFile(b"CONTENU-M2"))
        c = self.client_de(self.app_a)
        rep = c.get(reverse("formation:ressource_fichier", args=[r1.pk]))
        self.assertEqual(b"".join(rep.streaming_content), b"CONTENU-M1")
        self.assertEqual(c.get(reverse("formation:ressource_fichier", args=[r2.pk])).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("formation:ressource_fichier", args=[r1.pk])).status_code, 302)
        with self.assertRaises(ValueError):
            r1.fichier.url  # aucune URL publique pour un fichier privé
