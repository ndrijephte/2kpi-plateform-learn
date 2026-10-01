"""Vérifie la configuration SMTP : python manage.py tester_email adresse@exemple.org"""
from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Envoie un e-mail de test pour valider la configuration SMTP du .env."

    def add_arguments(self, parser):
        parser.add_argument("destinataire")

    def handle(self, destinataire, **options):
        self.stdout.write(f"Serveur : {settings.EMAIL_HOST or '(console)'}:{getattr(settings, 'EMAIL_PORT', '')} "
                          f"SSL={getattr(settings, 'EMAIL_USE_SSL', False)} TLS={getattr(settings, 'EMAIL_USE_TLS', False)}")
        try:
            send_mail("Test d'envoi — 2KPI Learn",
                      "Si tu lis ce message, l'envoi d'e-mails de la plateforme fonctionne.",
                      settings.DEFAULT_FROM_EMAIL, [destinataire], fail_silently=False)
        except Exception as e:
            raise CommandError(f"Échec de l'envoi : {e}")
        self.stdout.write(self.style.SUCCESS(f"E-mail envoyé à {destinataire}."))
