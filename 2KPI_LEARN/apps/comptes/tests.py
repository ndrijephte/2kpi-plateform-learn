import json
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from apps.comptes.models import Candidature
from apps.comptes.services import decouper_nom
from apps.core.test_utils import MDP, BaseTest
from apps.evaluation.models import Inscription

API = "/api/candidatures/"
VITRINE = "https://www.2kpinnov.org"


@override_settings(VITRINE_ORIGINS=[VITRINE])
class CandidaturesApiTests(BaseTest):
    donnees = {"nom": "Yao KOUASSI", "email": "yao@exemple.org", "telephone": "+225 07", "participants": 1,
               "message": "Bonjour", "session": "geoai-2026", "session_libelle": "GéoAI 2026"}

    def poster(self, **extra):
        return self.client.post(API, json.dumps({**self.donnees, **extra}), content_type="application/json",
                                HTTP_ORIGIN=VITRINE)

    def test_cors_preflight(self):
        r = self.client.options(API, HTTP_ORIGIN=VITRINE)
        self.assertEqual(r["Access-Control-Allow-Origin"], VITRINE)
        r = self.client.options(API, HTTP_ORIGIN="https://pirate.example")
        self.assertNotIn("Access-Control-Allow-Origin", r)

    def test_depot_rattache_promotion_et_previent(self):
        self.promo_a.code_vitrine = "geoai-2026"
        self.promo_a.save()
        r = self.poster()
        self.assertEqual(r.status_code, 201)
        c = Candidature.objects.get()
        self.assertEqual(c.promotion, self.promo_a)
        self.assertTrue(self.admin.notifications.filter(titre__contains="Yao KOUASSI").exists())
        self.assertIn("yao@exemple.org", [m.to[0] for m in mail.outbox])  # accusé de réception

    def test_validation_pot_de_miel_et_limite(self):
        self.assertEqual(self.poster(email="pas-un-email").status_code, 400)
        self.assertEqual(self.poster(site_web="http://spam").status_code, 201)
        self.assertFalse(Candidature.objects.filter(email="yao@exemple.org").exists())
        for _ in range(4):  # 1 envoi piégé + 4 = limite de 5 par heure atteinte
            self.assertEqual(self.poster().status_code, 201)
        self.assertEqual(self.poster().status_code, 429)


class CandidaturesAdminTests(BaseTest):
    def setUp(self):
        super().setUp()
        self.cand = Candidature.objects.create(nom_complet="Awa N'GUESSAN", email="awa@exemple.org",
                                               telephone="07", session_libelle="GéoAI")

    def test_accepter_cree_le_compte_et_invite(self):
        c = self.client_de(self.admin)
        c.post(reverse("comptes:candidatures"), {"candidature": self.cand.pk, "action": "accepter",
                                                 "promotion": self.promo_a.pk})
        self.cand.refresh_from_db()
        user = self.cand.utilisateur
        self.assertEqual(self.cand.statut, "acceptee")
        self.assertEqual((user.first_name, user.last_name), ("Awa", "N'GUESSAN"))
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.profil.role, "apprenant")
        self.assertTrue(Inscription.objects.filter(apprenant=user, promotion=self.promo_a).exists())
        invitation = mail.outbox[-1]
        self.assertIn("/reinitialiser/", invitation.body)
        lien = next(l for l in invitation.body.split() if "/reinitialiser/" in l)
        r = self.client.get(lien, follow=True)
        self.assertContains(r, "Choisis ton mot de passe")

    def test_refus_et_email(self):
        self.client_de(self.admin).post(reverse("comptes:candidatures"),
                                        {"candidature": self.cand.pk, "action": "refuser", "motif": "Complet"})
        self.cand.refresh_from_db()
        self.assertEqual(self.cand.statut, "refusee")
        self.assertIn("Complet", mail.outbox[-1].body)

    def test_decouper_nom(self):
        self.assertEqual(decouper_nom("KOUASSI Yao Jean"), ("Yao Jean", "KOUASSI"))
        self.assertEqual(decouper_nom("Yao Kouassi"), ("Yao", "Kouassi"))


class ProfilsTests(BaseTest):
    def test_chacun_modifie_son_profil(self):
        for user in (self.app_a, self.admin):
            r = self.client_de(user).post(reverse("comptes:profil_modifier"), {
                "c-first_name": "Nouveau", "c-last_name": "Nom", "c-email": f"{user.username}@neuf.org",
                "p-telephone": "0102"})
            self.assertEqual(r.status_code, 302)
            user.refresh_from_db()
            self.assertEqual((user.first_name, user.profil.telephone), ("Nouveau", "0102"))

    def test_admin_ne_peut_pas_se_retrograder(self):
        r = self.client_de(self.admin).post(reverse("comptes:utilisateur_editer", args=[self.admin.pk]), {
            "c-username": "admin_t", "c-first_name": "A", "c-last_name": "B", "c-email": "admin_t@exemple.org",
            "c-is_active": "on", "c-role": "apprenant"})
        self.assertContains(r, "ne peux ni retirer")


@override_settings(DEBUG=False)
class MotDePasseOublieTests(BaseTest):
    def demander(self, email):
        return self.client.post(reverse("password_reset"), {"email": email})

    def lien(self):
        return next(l for l in mail.outbox[-1].body.split() if "/reinitialiser/" in l)

    def test_email_complet_et_https(self):
        self.assertRedirects(self.demander("APP_A@exemple.org"), reverse("password_reset_done"))
        m = mail.outbox[-1]
        self.assertEqual(m.to, ["app_a@exemple.org"])
        self.assertTrue(m.subject.startswith("Réinitialisation de votre mot de passe 2KPI"), m.subject)
        self.assertIn("identifiant de connexion : app_a", m.body)
        self.assertTrue(self.lien().startswith("https://"))

    def test_compte_invite_sans_mot_de_passe(self):
        """Invitation expirée : l'apprenant doit pouvoir passer par « mot de passe oublié »."""
        self.app_b.set_unusable_password()
        self.app_b.save()
        self.demander("app_b@exemple.org")
        r = self.client.get(self.lien(), follow=True)
        r = self.client.post(r.redirect_chain[-1][0], {"new_password1": "Un-Nouveau-Mdp-2026", "new_password2":
                                                       "Un-Nouveau-Mdp-2026"}, follow=True)
        self.assertContains(r, "Accéder à mon espace")  # connecté directement après la définition
        self.app_b.refresh_from_db()
        self.assertTrue(self.app_b.check_password("Un-Nouveau-Mdp-2026"))

    def test_adresse_inconnue_et_limite(self):
        self.assertRedirects(self.demander("personne@exemple.org"), reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)
        for _ in range(4):  # 5 demandes par heure et par IP, adresse inconnue comprise
            self.demander("app_a@exemple.org")
        self.assertRedirects(self.demander("app_a@exemple.org"), reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 4)  # la 6e demande de l'heure n'envoie rien

    def test_connexion_par_email(self):
        r = self.client.post(reverse("login"), {"username": "App_A@Exemple.org", "password": MDP})
        self.assertRedirects(r, reverse("tableau_bord:accueil"), fetch_redirect_response=False)
