"""Envoi des e-mails en production (cPanel).

Sur un hébergement mutualisé, le SMTP authentifié échoue souvent pour des raisons invisibles
depuis l'application : mot de passe de boîte modifié, certificat de mail.<domaine> non valide,
port bloqué, quota… Django avale alors l'erreur du « mot de passe oublié » et la personne
ne reçoit jamais rien. Ce backend tente le SMTP puis, en cas d'échec, remet le message à
l'agent de messagerie local de l'hébergeur (/usr/sbin/sendmail → Exim sur cPanel), qui n'a
besoin ni de mot de passe ni de TLS. Chaque échec est journalisé dans logs/2kpi_learn.log.
"""
import logging
import os
import subprocess
from email.utils import parseaddr
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.backends.smtp import EmailBackend as SmtpBackend

logger = logging.getLogger("apps.mail")


def sendmail_disponible():
    chemin = getattr(settings, "EMAIL_SENDMAIL", "")
    return bool(chemin) and os.access(chemin, os.X_OK)


class SendmailBackend(BaseEmailBackend):
    """Remet chaque message au binaire sendmail du serveur (aucune authentification requise)."""

    def send_messages(self, messages):
        envoyes = 0
        for m in messages:
            destinataires = m.recipients()
            if not destinataires:
                continue
            expediteur = parseaddr(m.from_email or settings.DEFAULT_FROM_EMAIL)[1]
            try:
                subprocess.run([settings.EMAIL_SENDMAIL, "-i", "-f", expediteur, "--", *destinataires],
                               input=m.message().as_bytes(linesep="\n"), check=True, timeout=30,
                               capture_output=True)
                envoyes += 1
            except Exception as e:
                detail = getattr(e, "stderr", b"") or b""
                logger.error("sendmail : échec d'envoi à %s : %s %s", destinataires, e,
                             detail.decode(errors="replace").strip())
                if not self.fail_silently:
                    raise
        return envoyes


class SmtpAvecRepliBackend(SmtpBackend):
    """SMTP du .env ; si le serveur SMTP refuse ou est injoignable, repli sur sendmail."""

    def send_messages(self, messages):
        try:
            return SmtpBackend(fail_silently=False).send_messages(messages)
        except Exception as e:
            logger.error("SMTP %s:%s en échec (%s: %s)%s", settings.EMAIL_HOST, settings.EMAIL_PORT,
                         type(e).__name__, e, " - repli sur sendmail" if sendmail_disponible() else "")
            if sendmail_disponible():
                return SendmailBackend(fail_silently=self.fail_silently).send_messages(messages)
            if not self.fail_silently:
                raise
            return 0
