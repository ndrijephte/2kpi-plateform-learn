"""Importe la banque de questions GIFT (Test S1) dans un Quiz rattaché au module M1.
Idempotent (recrée les questions du quiz)."""
from pathlib import Path
from django.core.management.base import BaseCommand
from apps.formation.models import Module
from apps.evaluation.gift import importer_gift
from apps.evaluation.models import Quiz

DATA = Path(__file__).resolve().parents[2] / "data" / "Test_S1_banque_questions.gift"


class Command(BaseCommand):
    help = "Importe le Test S1 (GIFT) dans un quiz du module M1."

    def handle(self, *args, **options):
        module = Module.objects.filter(code="M1").first()
        if not module:
            self.stderr.write("Module M1 introuvable — lance d'abord `seed_geoai`.")
            return
        if not DATA.exists():
            self.stderr.write(f"Fichier GIFT introuvable : {DATA}")
            return
        quiz, _ = Quiz.objects.get_or_create(module=module, titre="Test — Semaine 1")
        n = importer_gift(quiz, DATA.read_text(encoding="utf-8"), remplacer=True)
        self.stdout.write(self.style.SUCCESS(f"OK — {n} questions importées dans « {quiz.titre} »."))
