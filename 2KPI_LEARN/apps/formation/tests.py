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
    @staticmethod
    def lignes(*docs, **cible):
        """Données POST de l'ajout groupé : une ligne par dict {titre, fichier, url, instructions, type}."""
        d = {"docs-TOTAL_FORMS": len(docs), "docs-INITIAL_FORMS": 0, **cible}
        for i, doc in enumerate(docs):
            d.update({f"docs-{i}-{k}": v for k, v in doc.items()})
        return d

    def test_depot_formats(self):
        c = self.client_de(self.form_a)
        s = self.m1.seances.first()
        noms = ("cours.pdf", "tp.ipynb", "donnees.zip", "couche.gpkg")
        r = c.post("/formation/ressources/ajouter/",
                   self.lignes(*({"fichier": SimpleUploadedFile(n, b"x")} for n in noms), seance=s.pk))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(sorted(Ressource.objects.values_list("type", flat=True)),
                         ["archive", "donnees", "notebook", "pdf"])
        for nom in ("page.html", "script.exe", "image.svg"):
            r = c.post("/formation/ressources/ajouter/",
                       self.lignes({"fichier": SimpleUploadedFile(nom, b"x")}, seance=s.pk))
            self.assertContains(r, "non autorisé")
        self.assertEqual(Ressource.objects.count(), 4)  # rien d'enregistré en cas d'erreur

    def test_ajout_groupe_pdf_notebook_meet(self):
        c = self.client_de(self.form_a)
        s = self.m1.seances.first()
        r = c.post("/formation/ressources/ajouter/", self.lignes(
            {"fichier": SimpleUploadedFile("support_cours.pdf", b"x"), "instructions": "A lire avant"},
            {"titre": "TP 1", "fichier": SimpleUploadedFile("tp1.ipynb", b"{}"),
             "url": "https://colab.research.google.com/drive/abc"},
            {"url": "https://meet.google.com/abc-defg-hij", "instructions": "Ouvert 10 min avant"},
            {},  # ligne laissée vide : ignorée
            seance=s.pk, next=f"/formation/seance/{s.pk}/"))
        self.assertRedirects(r, f"/formation/seance/{s.pk}/", fetch_redirect_response=False)
        pdf, tp, visio = Ressource.objects.filter(seance=s).order_by("ordre")
        self.assertEqual((pdf.titre, pdf.type, pdf.instructions), ("support cours", "pdf", "A lire avant"))
        self.assertEqual((tp.type, tp.colab_url, tp.url), ("notebook", "https://colab.research.google.com/drive/abc", ""))
        self.assertEqual((visio.type, visio.titre), ("visio", "Classe virtuelle"))
        self.assertEqual(pdf.ajoute_par, self.form_a)
        page = self.client_de(self.app_a).get(f"/formation/seance/{s.pk}/")
        self.assertContains(page, "Rejoindre le cours")
        self.assertContains(page, "https://meet.google.com/abc-defg-hij")
        self.assertContains(page, "Ouvrir dans Colab")

    def test_ajout_groupe_validation(self):
        c = self.client_de(self.form_a)
        s = self.m1.seances.first()
        self.assertContains(c.post("/formation/ressources/ajouter/", self.lignes({}, seance=s.pk)),
                            "Ajoute au moins un document")
        self.assertContains(c.post("/formation/ressources/ajouter/",
                                   self.lignes({"instructions": "sans fichier"}, seance=s.pk)),
                            "Ajoute un fichier ou un lien")
        self.assertContains(c.post("/formation/ressources/ajouter/",
                                   self.lignes({"url": "javascript:alert(1)"}, seance=s.pk)), "URL")
        self.assertContains(c.post("/formation/ressources/ajouter/",
                                   self.lignes({"url": "https://zoom.us/j/1"}, seance=s.pk, module=self.m1.pk)),
                            "un seul des deux")
        self.assertFalse(Ressource.objects.exists())

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
