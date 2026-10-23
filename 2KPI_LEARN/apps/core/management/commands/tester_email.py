"""Diagnostic complet de l'envoi d'e-mails : python manage.py tester_email adresse@exemple.org

Vérifie étape par étape (DNS, connexion, TLS, authentification, envoi) le SMTP du .env, puis le
sendmail de l'hébergeur, et rejoue le « mot de passe oublié » pour l'adresse donnée (--reinitialisation).
Chaque échec est accompagné de la correction la plus probable.
"""
import os
import smtplib
import socket
import ssl
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand, CommandError

CONSEILS = {
    smtplib.SMTPRecipientsRefused: "Adresse destinataire refusée (domaine inexistant ?) : teste avec une vraie adresse.",
    smtplib.SMTPSenderRefused: "Expéditeur refusé : DEFAULT_FROM_EMAIL doit utiliser la boîte de EMAIL_HOST_USER "
                               "(ex. 2KPI Learn <no-reply@2kpinnov.org>).",
    smtplib.SMTPAuthenticationError: "Identifiants refusés : EMAIL_HOST_USER = adresse COMPLÈTE de la boîte "
                                     "(no-reply@2kpinnov.org) ; retape le mot de passe de la boîte dans cPanel "
                                     "› Comptes de messagerie, puis dans .env.",
    ssl.SSLCertVerificationError: "Certificat du serveur mail invalide pour ce nom : mets EMAIL_HOST = le nom "
                                  "du serveur indiqué dans cPanel › Connect Devices (ex. serveurXX.hebergeur.com), "
                                  "ou EMAIL_ENVOI=sendmail.",
    ssl.SSLError: "Échec TLS : 465 ⇒ EMAIL_USE_SSL=True ; 587 ⇒ EMAIL_USE_TLS=True (pas les deux).",
    socket.timeout: "Port bloqué (sur cPanel : « SMTP Restrictions » empêche souvent les applis d'ouvrir une "
                    "connexion SMTP) ou mauvais port : essaie 465 / 587, ou EMAIL_ENVOI=sendmail.",
    ConnectionRefusedError: "Port fermé sur ce serveur : essaie 465 ou 587, ou EMAIL_HOST=localhost port 25.",
    socket.gaierror: "Nom de serveur inconnu : vérifie EMAIL_HOST (ex. mail.2kpinnov.org, sans « https:// »).",
}


def conseil(e):
    for type_, texte in CONSEILS.items():
        if isinstance(e, type_):
            return texte
    return "Consulte le message ci-dessus ; en dernier recours : EMAIL_ENVOI=sendmail dans .env."


class Command(BaseCommand):
    help = "Diagnostique et teste l'envoi d'e-mails (SMTP, sendmail, mot de passe oublié)."

    def add_arguments(self, parser):
        parser.add_argument("destinataire")
        parser.add_argument("--reinitialisation", action="store_true",
                            help="Rejoue aussi « mot de passe oublié » pour cette adresse (envoie le vrai lien).")

    def ok(self, texte):
        self.stdout.write(self.style.SUCCESS(f"  ✔ {texte}"))

    def ko(self, texte, e=None):
        self.stdout.write(self.style.ERROR(f"  ✘ {texte}" + (f" - {type(e).__name__}: {e}" if e else "")))
        if e is not None:
            self.stdout.write(self.style.WARNING(f"    → {conseil(e)}"))

    def handle(self, destinataire, reinitialisation=False, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Configuration lue"))
        for nom in ("EMAIL_ENVOI", "EMAIL_BACKEND", "EMAIL_HOST", "EMAIL_PORT", "EMAIL_USE_SSL", "EMAIL_USE_TLS",
                    "EMAIL_HOST_USER", "DEFAULT_FROM_EMAIL"):
            source = " (variable d'environnement : prioritaire sur .env !)" if nom in os.environ else ""
            self.stdout.write(f"  {nom} = {getattr(settings, nom, '')!r}{source}")
        self.stdout.write(f"  EMAIL_HOST_PASSWORD = {'(renseigné, ' + str(len(settings.EMAIL_HOST_PASSWORD)) + ' caractères)' if settings.EMAIL_HOST_PASSWORD else '(VIDE)'}")
        if "console" in settings.EMAIL_BACKEND:
            self.stdout.write(self.style.WARNING("  Mode console : les e-mails ne partent pas, ils s'affichent dans le "
                                                 "terminal. Renseigne EMAIL_HOST (ou EMAIL_ENVOI=sendmail) dans .env."))

        resultats = {}
        if settings.EMAIL_HOST:
            resultats["smtp"] = self.tester_smtp(destinataire)
        resultats["sendmail"] = self.tester_sendmail(destinataire)

        self.stdout.write(self.style.MIGRATE_HEADING("Bilan"))
        mode = settings.EMAIL_BACKEND.rsplit(".", 1)[-1]
        if resultats.get("smtp"):
            self.ok(f"SMTP opérationnel (backend actif : {mode}).")
        elif resultats.get("sendmail"):
            self.ok(f"SMTP indisponible mais sendmail fonctionne : le backend {mode} bascule seul dessus"
                    if "Repli" in mode or "Sendmail" in mode else "sendmail fonctionne : mets EMAIL_ENVOI=sendmail")
        else:
            self.ko("Aucun moyen d'envoi ne fonctionne.")
        self.stdout.write("  Pense à redémarrer l'app après toute modification du .env "
                          "(Setup Python App › Restart, ou : touch tmp/restart.txt).")

        if reinitialisation:
            self.rejouer_reinitialisation(destinataire)
        if not any(resultats.values()):
            raise CommandError("Envoi impossible : corrige la configuration ci-dessus.")

    def tester_smtp(self, destinataire):
        hote, port = settings.EMAIL_HOST, settings.EMAIL_PORT
        self.stdout.write(self.style.MIGRATE_HEADING(f"SMTP {hote}:{port}"))
        try:
            ip = socket.gethostbyname(hote)
            self.ok(f"DNS : {hote} → {ip}")
        except Exception as e:
            self.ko("Résolution DNS", e)
            return False
        try:
            classe = smtplib.SMTP_SSL if settings.EMAIL_USE_SSL else smtplib.SMTP
            kw = {"context": ssl.create_default_context()} if settings.EMAIL_USE_SSL else {}
            with classe(hote, port, timeout=settings.EMAIL_TIMEOUT, **kw) as s:
                self.ok("Connexion" + (" SSL" if settings.EMAIL_USE_SSL else ""))
                s.ehlo()
                if settings.EMAIL_USE_TLS:
                    s.starttls(context=ssl.create_default_context())
                    s.ehlo()
                    self.ok("STARTTLS")
                if settings.EMAIL_HOST_USER:
                    s.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
                    self.ok(f"Authentification ({settings.EMAIL_HOST_USER})")
                m = EmailMessage("Test SMTP - 2KPI Learn", "Si tu lis ce message, le SMTP de la plateforme fonctionne.",
                                 settings.DEFAULT_FROM_EMAIL, [destinataire]).message()
                refus = s.sendmail(settings.EMAIL_HOST_USER or settings.DEFAULT_FROM_EMAIL, [destinataire],
                                   m.as_bytes())
                if refus:
                    self.ko(f"Destinataire refusé : {refus}")
                    return False
                self.ok(f"Message accepté par le serveur pour {destinataire} (vérifie aussi les spams)")
                return True
        except Exception as e:
            self.ko("Échec SMTP", e)
            return False

    def tester_sendmail(self, destinataire):
        from apps.core.mail import SendmailBackend, sendmail_disponible
        self.stdout.write(self.style.MIGRATE_HEADING(f"sendmail local ({settings.EMAIL_SENDMAIL})"))
        if not sendmail_disponible():
            self.stdout.write("  – absent sur cette machine (normal en local, présent sur cPanel)")
            return False
        try:
            SendmailBackend(fail_silently=False).send_messages([EmailMessage(
                "Test sendmail - 2KPI Learn", "Si tu lis ce message, l'envoi via le serveur (sendmail) fonctionne.",
                settings.DEFAULT_FROM_EMAIL, [destinataire])])
            self.ok(f"Message remis à sendmail pour {destinataire} (vérifie aussi les spams)")
            return True
        except Exception as e:
            self.ko("Échec sendmail", e)
            return False

    def rejouer_reinitialisation(self, email):
        from django.contrib.auth import get_user_model
        from django.test import RequestFactory
        from apps.comptes.forms import MotDePasseOublieForm
        self.stdout.write(self.style.MIGRATE_HEADING(f"« Mot de passe oublié » pour {email}"))
        comptes = get_user_model().objects.filter(email__iexact=email)
        if not comptes:
            self.ko("Aucun compte n'a cette adresse : rien ne serait envoyé (comportement normal, la page "
                    "affiche quand même « e-mail envoyé »). Vérifie l'e-mail du compte dans Utilisateurs.")
            return
        for u in comptes:
            etat = "actif" if u.is_active else "DÉSACTIVÉ (aucun e-mail ne part)"
            self.stdout.write(f"  compte « {u.username} » : {etat}")
        hote = next((h for h in settings.ALLOWED_HOSTS if h not in ("*", "") and not h.startswith(".")), "localhost")
        form = MotDePasseOublieForm({"email": email})
        form.is_valid()
        form.save(request=RequestFactory().get("/", HTTP_HOST=hote), use_https=not settings.DEBUG,
                  subject_template_name="registration/password_reset_subject.txt",
                  email_template_name="registration/password_reset_email.html")
        if getattr(form, "echecs", 0):
            self.ko("L'e-mail de réinitialisation n'a pas pu partir (détail dans logs/2kpi_learn.log).")
        elif getattr(form, "nb_comptes", 0):
            self.ok(f"Lien de réinitialisation envoyé (liens en https://{hote}/…)")
