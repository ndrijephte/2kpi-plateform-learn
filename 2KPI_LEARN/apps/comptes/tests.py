import json
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from apps.agenda.models import Promotion
from apps.comptes.models import Candidature
from apps.comptes.services import decouper_nom
from apps.core.test_utils import MDP, BaseTest
from apps.evaluation.models import Inscription

User = get_user_model()
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
        accepter = {"candidature": self.cand.pk, "action": "accepter", "promotion": self.promo_a.pk}
        c.post(reverse("comptes:candidatures"), accepter)  # promotion encore planifiée : refusé
        self.cand.refresh_from_db()
        self.assertEqual(self.cand.statut, "nouvelle")
        self.promo_a.statut = Promotion.Statut.INSCRIPTIONS
        self.promo_a.save()
        c.post(reverse("comptes:candidatures"), accepter)
        self.cand.refresh_from_db()
        user = self.cand.utilisateur
        self.assertEqual(self.cand.statut, "acceptee")
        self.assertEqual(Inscription.objects.get(apprenant=user).statut, Inscription.Statut.ADMISE)
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
        for _ in range(4):  # 3 demandes par heure et par adresse e-mail
            self.assertRedirects(self.demander("app_a@exemple.org"), reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 3)
        self.demander("app_b@exemple.org")  # une autre adresse n'est pas bloquée
        self.assertEqual(len(mail.outbox), 4)

    def test_echec_smtp_journalise(self):
        with self.settings(EMAIL_BACKEND="apps.comptes.tests.BackendEnPanne"), \
                self.assertLogs("apps.comptes.forms", "ERROR") as journal:
            self.assertRedirects(self.demander("app_a@exemple.org"), reverse("password_reset_done"))
        self.assertIn("ÉCHEC d'envoi à app_a@exemple.org", journal.output[0])

    def test_connexion_par_email(self):
        r = self.client.post(reverse("login"), {"username": "App_A@Exemple.org", "password": MDP})
        self.assertRedirects(r, reverse("tableau_bord:accueil"), fetch_redirect_response=False)


class BackendEnPanne:
    def __init__(self, *a, **kw):
        pass

    def send_messages(self, messages):
        raise ConnectionRefusedError("SMTP injoignable")


class CreationCompteTests(BaseTest):
    URL = "/creer-mon-compte/"

    def donnees(self, **kw):
        return {"categorie": "etudiant", "first_name": "Awa", "last_name": "KONÉ", "email": "Awa.Kone@Exemple.org",
                "telephone": "+225 07 00 00 00", "structure": "Université FHB", "password1": "Geomatique-2026!",
                "password2": "Geomatique-2026!", **kw}

    def test_lien_depuis_la_connexion(self):
        self.assertContains(self.client.get(reverse("login")), 'href="/creer-mon-compte/"')

    def test_creation_connexion_et_notification(self):
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post(self.URL, self.donnees(), follow=True)
        self.assertContains(r, "Votre compte est créé")
        u = User.objects.get(email="awa.kone@exemple.org")
        self.assertEqual((u.username, u.profil.role, u.profil.categorie, u.profil.structure),
                         ("awakone", "apprenant", "etudiant", "Université FHB"))
        self.assertTrue(u.check_password("Geomatique-2026!"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), u.pk)
        self.assertContains(r, "Aucune inscription active")  # aucun contenu sans promotion validée
        self.assertEqual(mail.outbox[-1].to, ["awa.kone@exemple.org"])
        self.assertTrue(self.admin.notifications.filter(titre__contains="Awa").exists())

    def test_session_choisie_devient_candidature(self):
        self.promo_a.publiee_vitrine, self.promo_a.code_vitrine = True, "geoai-a"
        self.promo_a.statut = Promotion.Statut.INSCRIPTIONS
        self.promo_a.save()
        r = self.client.get(self.URL + "?session=geoai-a")
        self.assertEqual(r.context["form"]["promotion"].value(), self.promo_a.pk)
        r = self.client.post(self.URL, self.donnees(categorie="professionnel", promotion=self.promo_a.pk), follow=True)
        self.assertContains(r, "Inscription en cours de validation")
        c = Candidature.objects.get(email="awa.kone@exemple.org")
        self.assertEqual((c.promotion, c.utilisateur.email, c.statut), (self.promo_a, c.email, "nouvelle"))
        # L'admin accepte : le compte existant est rattaché, sans nouvelle invitation à définir un mot de passe
        self.client.force_login(self.admin)
        self.client.post(reverse("comptes:candidatures"), {"candidature": c.pk, "action": "accepter",
                                                           "promotion": self.promo_a.pk})
        self.assertTrue(Inscription.objects.filter(apprenant=c.utilisateur, promotion=self.promo_a).exists())
        self.assertIn("nouvelle session", mail.outbox[-1].subject)

    def test_erreurs(self):
        r = self.client.post(self.URL, self.donnees(email="APP_A@exemple.org", password2="autre"))
        self.assertContains(r, "Un compte existe déjà avec cet e-mail")
        self.assertContains(r, "ne correspondent pas")
        r = self.client.post(self.URL, self.donnees(password1="12345678", password2="12345678"))
        self.assertFalse(User.objects.filter(email="awa.kone@exemple.org").exists())

    def test_robot_et_limite(self):
        self.client.post(self.URL, self.donnees(site_web="http://spam"))
        self.assertFalse(User.objects.filter(email="awa.kone@exemple.org").exists())
        for i in range(6):
            self.client.post(self.URL, self.donnees(email=f"robot{i}@exemple.org"))
            self.client.logout()
        self.assertEqual(User.objects.filter(email__startswith="robot").count(), 5)

    def test_deja_connecte(self):
        self.client.force_login(self.app_a)
        self.assertRedirects(self.client.get(self.URL), reverse("tableau_bord:accueil"), fetch_redirect_response=False)


class FormulaireFormateurTests(BaseTest):
    """Fiche d'un formateur : une ou plusieurs promotions, sans champs d'apprenant."""

    def _post(self, cible, **extra):
        data = {"c-username": cible.username, "c-first_name": cible.first_name, "c-last_name": "",
                "c-email": cible.email, "c-is_active": "on", "c-role": "formateur",
                "p-telephone": "", "p-structure": "", "p-specialite": "", "p-bio": ""}
        data.update(extra)
        return self.client_de(self.admin).post(reverse("comptes:utilisateur_editer", args=[cible.pk]), data)

    def test_associer_plusieurs_promotions(self):
        from apps.agenda.models import Affectation
        from apps.core.permissions import interventions
        cible = self.compte("form_c", "formateur")
        r = self._post(cible, **{"c-promotions_formateur": [self.promo_a.pk, self.promo_b.pk]})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(set(Affectation.objects.filter(formateur=cible).values_list("promotion", flat=True)),
                         {self.promo_a.pk, self.promo_b.pk})
        self.assertTrue(all(a.tous_les_modules for a in Affectation.objects.filter(formateur=cible)))
        cible.refresh_from_db()
        self.assertEqual(interventions(cible), {self.promo_a.pk: None, self.promo_b.pk: None})
        self.assertTrue(cible.notifications.filter(titre__icontains="promotion").exists())
        # La fiche réaffiche les promotions cochées
        page = self.client_de(self.admin).get(reverse("comptes:utilisateur_editer", args=[cible.pk]))
        self.assertEqual({p.pk for p in page.context["compte_form"].initial["promotions_formateur"]},
                         {self.promo_a.pk, self.promo_b.pk})
        # Décocher une promotion retire l'accès
        self._post(cible, **{"c-promotions_formateur": [self.promo_b.pk]})
        self.assertEqual(list(Affectation.objects.filter(formateur=cible).values_list("promotion", flat=True)),
                         [self.promo_b.pk])

    def test_affectation_module_par_module_conservee(self):
        from apps.agenda.models import Affectation
        a = Affectation.objects.create(promotion=self.promo_a, formateur=self.form_b)
        a.modules.set([self.m2])
        self._post(self.form_b, **{"c-promotions_formateur": [self.promo_a.pk, self.promo_b.pk]})
        a.refresh_from_db()
        self.assertFalse(a.tous_les_modules)
        self.assertEqual(list(a.modules.all()), [self.m2])

    def test_referent_decoche(self):
        self._post(self.form_a, **{"c-promotions_formateur": []})
        self.promo_a.refresh_from_db()
        self.assertIsNone(self.promo_a.formateur)

    def test_champs_selon_le_role(self):
        r = self.client_de(self.admin).get(reverse("comptes:utilisateur_editer", args=[self.form_a.pk]))
        self.assertContains(r, 'data-role="apprenant"')   # masqués à l'écran pour un formateur
        self.assertContains(r, 'data-role="formateur"')
        self.assertNotIn("categorie", self.client_de(self.form_a).get(reverse("comptes:profil_modifier"))
                         .context["profil_form"].fields)
        # La promotion d'apprenant ne s'applique pas à un formateur
        self._post(self.form_a, **{"c-promotion": self.promo_b.pk, "c-promotions_formateur": [self.promo_a.pk]})
        self.assertFalse(Inscription.objects.filter(apprenant=self.form_a).exists())

    def test_creation_formateur_avec_promotions(self):
        from apps.agenda.models import Affectation
        r = self.client_de(self.admin).post(reverse("comptes:utilisateurs"), {
            "first_name": "Awa", "last_name": "K", "email": "awa@exemple.org", "username": "awa",
            "role": "formateur", "password": MDP, "promotions_formateur": [self.promo_a.pk]})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Affectation.objects.filter(formateur__username="awa", promotion=self.promo_a).exists())
        liste = self.client_de(self.admin).get(reverse("comptes:utilisateurs") + "?role=formateur")
        self.assertContains(liste, "Promo A")


class AdministrateurHorsRolesTests(BaseTest):
    """L'administrateur n'est ni apprenant ni formateur : jamais référent, affecté ni présenté comme tel."""

    def test_admin_ni_referent_ni_affecte(self):
        from apps.agenda.models import Affectation
        from apps.core.permissions import appliquer_role
        self.promo_b.formateur = self.admin
        self.promo_b.save()
        Affectation.objects.create(promotion=self.promo_a, formateur=self.admin, tous_les_modules=True)
        appliquer_role(self.admin, "admin")
        self.promo_b.refresh_from_db()
        self.assertIsNone(self.promo_b.formateur)
        self.assertFalse(Affectation.objects.filter(formateur=self.admin).exists())
        r = self.client_de(self.admin).get(reverse("agenda:promotions"))
        self.assertNotIn(self.admin, r.context["formateurs"])
        self.assertIn(self.form_a, r.context["formateurs"])

    def test_super_utilisateur_toujours_admin(self):
        from apps.core.permissions import appliquer_role
        su = User.objects.create_superuser("racine", "racine@exemple.org", MDP)
        appliquer_role(su, "formateur")
        su.profil.refresh_from_db()
        self.assertEqual(su.profil.role, "admin")

    def test_fiche_admin_sans_champs_formateur_ni_apprenant(self):
        r = self.client_de(self.admin).get(reverse("comptes:utilisateur_editer", args=[self.admin.pk]))
        html = r.content.decode()
        for champ in ("c-promotions_formateur", "c-promotion", "p-categorie"):
            debut = html.index(f'name="{champ}"')
            self.assertIn("hidden", html[html.rindex('<div class="field"', 0, debut):debut], champ)
        self.assertNotContains(self.client_de(self.admin).get(reverse("comptes:profil")), "Aucune promotion confiée")


class DiagnosticAccesTests(BaseTest):
    """L'admin voit pourquoi un apprenant accède ou non aux cours."""

    def test_diagnostic_explique_le_blocage(self):
        from apps.formation.acces import diagnostic_apprenant
        self.assertTrue(diagnostic_apprenant(self.app_a)["ok"])
        self.assertEqual(diagnostic_apprenant(self.app_a)["ouverts"], ["M1"])
        d = diagnostic_apprenant(self.app_b)
        self.assertFalse(d["ok"])
        self.assertIn("M1 (Promo A)", d["etapes"][-1][2])  # ouvert ailleurs, pas pour Promo B
        r = self.client_de(self.admin).get(reverse("comptes:utilisateur_editer", args=[self.app_b.pk]))
        self.assertContains(r, "Accès aux cours")
        self.assertContains(r, "Aucun module ouvert pour « Promo B »")
        self.assertContains(self.client_de(self.admin).get(reverse("comptes:utilisateurs")), "Pas d'accès aux cours")
        self.insc_a.statut = Inscription.Statut.ADMISE
        self.insc_a.save()
        self.assertIn("Confirme-la", diagnostic_apprenant(self.app_a)["etapes"][-1][2])

    def test_inscription_plus_recente_ne_masque_pas_le_cours(self):
        from apps.formation.models import Formation
        autre = Formation.objects.create(titre="WebSIG")
        Inscription.objects.create(apprenant=self.app_a, formation=autre, statut=Inscription.Statut.VALIDEE)
        seance = self.m1.seances.first()
        c = self.client_de(self.app_a)
        self.assertEqual(c.get(reverse("formation:seance", args=[seance.pk])).status_code, 200)
        self.assertEqual(c.get(reverse("formation:modules")).context["formation"], self.formation)
