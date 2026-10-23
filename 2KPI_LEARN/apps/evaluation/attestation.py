"""Attestation de réussite : numéro public attribué à la validation, PDF généré à la demande.

Le numéro (ex. 2KPI-7HQ4-K9MT) figure sur le PDF avec un QR code renvoyant à la page publique
de vérification (/attestation/<numéro>/) : un tiers (employeur, université) contrôle qu'elle est
authentique et toujours valide. Rien n'est stocké : le PDF est recalculé à chaque téléchargement.
"""
import io
import secrets
from pathlib import Path
from django.conf import settings
from django.utils import timezone
from django.utils.formats import date_format

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sans 0/O ni 1/I/L : lisible et recopiable


def nouveau_code():
    from .models import Inscription
    while True:
        brut = "".join(secrets.choice(ALPHABET) for _ in range(8))
        code = f"2KPI-{brut[:4]}-{brut[4:]}"
        if not Inscription.objects.filter(code_attestation=code).exists():
            return code


def delivrer(inscription):
    """Attribue le numéro d'attestation (une seule fois : il reste stable ensuite)."""
    if not inscription.code_attestation:
        inscription.code_attestation = nouveau_code()
        inscription.date_attestation = timezone.localdate()
        inscription.save(update_fields=["code_attestation", "date_attestation"])
    return inscription


def est_valide(inscription):
    return bool(inscription.code_attestation) and inscription.statut == inscription.Statut.VALIDEE


def periode(inscription):
    """(début, fin) de la formation suivie : début de la promotion → dernière séance réalisée."""
    promo = inscription.promotion
    if promo is None:
        return inscription.date_debut, inscription.date_attestation
    derniere = promo.evenements.filter(statut="realise").order_by("-date_debut").first()
    fin = timezone.localtime(derniere.date_debut).date() if derniere else inscription.date_attestation
    return promo.date_debut, fin


def _logo(parametres):
    """Chemin d'une image lisible par ReportLab (PNG/JPG) : logo déposé, sinon logo officiel."""
    if parametres.logo and Path(parametres.logo.name).suffix.lower() in (".png", ".jpg", ".jpeg"):
        try:
            return parametres.logo.path
        except (NotImplementedError, ValueError):
            pass
    return str(Path(settings.BASE_DIR) / "static" / "img" / "logo-2kpi.png")


def pdf(inscription, url_verification):
    """PDF A4 paysage de l'attestation (bytes)."""
    from reportlab.graphics import renderPDF
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    from apps.core.models import Parametres

    p = Parametres.charger()
    navy, corail, gris = HexColor("#16324a"), HexColor("#ef6a52"), HexColor("#5b6b77")
    largeur, hauteur = landscape(A4)
    tampon = io.BytesIO()
    c = canvas.Canvas(tampon, pagesize=(largeur, hauteur))
    apprenant = inscription.apprenant
    nom = (apprenant.get_full_name() or apprenant.username).strip()
    c.setTitle(f"Attestation — {nom}")
    c.setAuthor(p.organisme)

    # Cadre
    c.setStrokeColor(navy)
    c.setLineWidth(3)
    c.rect(28, 28, largeur - 56, hauteur - 56)
    c.setStrokeColor(corail)
    c.setLineWidth(1)
    c.rect(38, 38, largeur - 76, hauteur - 76)

    # Logo
    try:
        image = ImageReader(_logo(p))
        iw, ih = image.getSize()
        h = 62
        c.drawImage(image, 64, hauteur - 64 - h, width=h * iw / ih, height=h, mask="auto")
    except Exception:  # un logo illisible ne doit pas empêcher l'attestation
        pass
    c.setFont("Helvetica", 9)
    c.setFillColor(gris)
    c.drawRightString(largeur - 64, hauteur - 70, f"N° {inscription.code_attestation}")

    centre = largeur / 2
    y = hauteur - 165
    c.setFillColor(corail)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(centre, y + 44, p.organisme.upper())
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(centre, y, "ATTESTATION DE RÉUSSITE")

    c.setFillColor(gris)
    c.setFont("Helvetica", 13)
    c.drawCentredString(centre, y - 44, f"{p.organisme} atteste que")
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 26)
    c.drawCentredString(centre, y - 84, nom)
    c.setFillColor(gris)
    c.setFont("Helvetica", 13)
    c.drawCentredString(centre, y - 116, "a suivi avec succès la formation")
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 18)
    titre = inscription.formation.titre
    c.drawCentredString(centre, y - 146, titre if len(titre) <= 70 else titre[:68] + "…")

    debut, fin = periode(inscription)
    c.setFillColor(gris)
    c.setFont("Helvetica", 11.5)
    details = []
    if inscription.promotion:
        details.append(inscription.promotion.nom)
    if debut and fin:
        details.append(f"du {date_format(debut, 'j F Y')} au {date_format(fin, 'j F Y')}")
    c.drawCentredString(centre, y - 174, " · ".join(details))
    chiffres = []
    if inscription.heures_suivies:
        chiffres.append(f"{inscription.heures_suivies:g} heures suivies".replace(".", ","))
    if inscription.taux_assiduite is not None:
        chiffres.append(f"assiduité {inscription.taux_assiduite} %")
    if inscription.note_finale is not None:
        chiffres.append(f"note finale {inscription.note_finale:.2f}/20".replace(".", ","))
    c.drawCentredString(centre, y - 194, " · ".join(chiffres))

    # Signature
    c.setFillColor(navy)
    c.setFont("Helvetica", 11)
    lieu = f"Fait à {p.lieu_signature}, le " if p.lieu_signature else "Le "
    c.drawString(largeur - 300, 128, lieu + date_format(inscription.date_attestation or timezone.localdate(), "j F Y"))
    c.setFont("Helvetica-Bold", 11)
    if p.signataire_nom:
        c.drawString(largeur - 300, 108, p.signataire_nom)
    c.setFont("Helvetica", 10)
    c.setFillColor(gris)
    if p.signataire_fonction:
        c.drawString(largeur - 300, 94, p.signataire_fonction)
    c.setStrokeColor(gris)
    c.setLineWidth(0.5)
    c.line(largeur - 300, 70, largeur - 80, 70)

    # Vérification : QR code + adresse
    qr = QrCodeWidget(url_verification)
    x0, y0, x1, y1 = qr.getBounds()
    taille = 78
    dessin = Drawing(taille, taille, transform=[taille / (x1 - x0), 0, 0, taille / (y1 - y0), 0, 0])
    dessin.add(qr)
    renderPDF.draw(dessin, c, 64, 58)
    c.setFont("Helvetica", 8.5)
    c.setFillColor(gris)
    c.drawString(152, 100, "Authenticité vérifiable en ligne :")
    c.setFillColor(navy)
    c.drawString(152, 87, url_verification)
    c.setFillColor(gris)
    c.drawString(152, 74, f"Numéro {inscription.code_attestation}")

    c.showPage()
    c.save()
    return tampon.getvalue()
