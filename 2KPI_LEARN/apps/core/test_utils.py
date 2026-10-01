"""Socle commun des tests : données GéoAI, comptes par rôle, dossiers de fichiers temporaires."""
import datetime as dt
import shutil
import tempfile
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from apps.agenda.models import AccesModule, Promotion
from apps.agenda.services import generer_agenda
from apps.core.permissions import appliquer_role
from apps.evaluation.models import Inscription
from apps.formation.models import Formation

User = get_user_model()
MDP = "Mot-De-Passe-Test-2026!"
_TMP = tempfile.mkdtemp(prefix="2kpi-tests-")


@override_settings(MEDIA_ROOT=f"{_TMP}/media", PRIVATE_ROOT=f"{_TMP}/prive",
                   EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   SECURE_SSL_REDIRECT=False)
class BaseTest(TestCase):
    """Formation GéoAI (12 modules, 48 séances, quiz S1), un admin, deux formateurs,
    deux apprenants inscrits dans deux promotions (M1 ouvert pour la promotion A)."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_geoai", stdout=open("/dev/null", "w"))
        call_command("import_gift", stdout=open("/dev/null", "w"))
        cls.formation = Formation.objects.get(slug="geoai-sassandra")
        cls.m1 = cls.formation.modules.get(code="M1")
        cls.m2 = cls.formation.modules.get(code="M2")
        cls.admin = cls.compte("admin_t", "admin")
        cls.form_a = cls.compte("form_a", "formateur")
        cls.form_b = cls.compte("form_b", "formateur")
        cls.app_a = cls.compte("app_a", "apprenant")
        cls.app_b = cls.compte("app_b", "apprenant")
        lundi = timezone.localdate() - dt.timedelta(days=timezone.localdate().weekday())
        cls.promo_a = Promotion.objects.create(formation=cls.formation, nom="Promo A", date_debut=lundi + dt.timedelta(weeks=4),
                                               formateur=cls.form_a)
        cls.promo_b = Promotion.objects.create(formation=cls.formation, nom="Promo B", date_debut=lundi + dt.timedelta(weeks=4),
                                               formateur=cls.form_b)
        generer_agenda(cls.promo_a)
        generer_agenda(cls.promo_b)
        cls.insc_a = Inscription.objects.create(apprenant=cls.app_a, formation=cls.formation, promotion=cls.promo_a)
        cls.insc_b = Inscription.objects.create(apprenant=cls.app_b, formation=cls.formation, promotion=cls.promo_b)
        AccesModule.objects.create(promotion=cls.promo_a, module=cls.m1, etat=AccesModule.Etat.OUVERT)

    @classmethod
    def compte(cls, username, role, **extra):
        u = User.objects.create_user(username, f"{username}@exemple.org", MDP,
                                     first_name=username.capitalize(), **extra)
        appliquer_role(u, role)
        return u

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_TMP, ignore_errors=True)

    def setUp(self):
        cache.clear()

    def client_de(self, user):
        self.client.force_login(user)
        return self.client
