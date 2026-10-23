"""Prérequis et grille d'évaluation, définis par formation (Paramètres › Formations).

- Prérequis : chaque formation liste les siens ; l'état de l'apprenant est porté par son inscription
  (PrerequisInscription, absence = « à faire »). Les obligatoires conditionnent la confirmation.
- Grille : critères pondérés notés sur 20 (NoteCritere) → note de projet. La note finale combine
  contrôle continu, projet et soutenance selon les poids de la formation (note_finale()).
"""
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from .models import NoteCritere, PrerequisInscription

A_FAIRE = PrerequisInscription.Statut.A_FAIRE
OK = PrerequisInscription.Statut.OK


def _arrondi(x):
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ---------- Prérequis ----------

def etats_prerequis(inscription):
    """[(PrerequisFormation, statut)] dans l'ordre de la formation."""
    if inscription is None:
        return []
    etats = dict(inscription.prerequis.values_list("prerequis_id", "statut"))
    return [(p, etats.get(p.pk, A_FAIRE)) for p in inscription.formation.prerequis.all()]


@transaction.atomic
def definir_prerequis(inscription, statuts):
    """statuts : {prerequis_id: statut}. Les prérequis hors formation sont ignorés."""
    valides = set(inscription.formation.prerequis.values_list("pk", flat=True))
    for pid, statut in statuts.items():
        if pid in valides and statut in PrerequisInscription.Statut.values:
            PrerequisInscription.objects.update_or_create(inscription=inscription, prerequis_id=pid,
                                                          defaults={"statut": statut})


def obligatoires_manquants(inscription):
    """Libellés des prérequis obligatoires pas encore « OK »."""
    return [p.libelle for p, statut in etats_prerequis(inscription) if p.obligatoire and statut != OK]


# ---------- Grille d'évaluation et note finale ----------

def notes_criteres(inscription):
    """{critere_id: note} des critères notés."""
    return dict(inscription.notes_criteres.values_list("critere_id", "note_sur_20"))


def note_projet(inscription, criteres=None, notes=None):
    """Moyenne pondérée des critères (un critère non noté compte 0) ; None si la formation n'a pas de grille."""
    criteres = list(inscription.formation.criteres.all()) if criteres is None else criteres
    if not criteres:
        return None
    notes = notes_criteres(inscription) if notes is None else notes
    total = sum(c.poids for c in criteres)
    return _arrondi(sum(Decimal(notes.get(c.pk, 0)) * c.poids for c in criteres) / total)


def composantes(formation, a_une_grille):
    """[(clé, libellé, poids)] des composantes de la note finale qui s'appliquent à la formation."""
    parts = [("continu", "Contrôle continu", formation.poids_continu),
             ("projet", "Projet", formation.poids_projet if a_une_grille else 0),
             ("soutenance", "Soutenance", formation.poids_soutenance)]
    return [p for p in parts if p[2]]


def note_finale(formation, continu, projet, soutenance):
    """Moyenne des composantes applicables, pondérée par les poids de la formation (note absente = 0)."""
    valeurs = {"continu": continu, "projet": projet, "soutenance": soutenance}
    parts = composantes(formation, projet is not None)
    total = sum(poids for _, _, poids in parts)
    if not total:
        return _arrondi(0)
    return _arrondi(sum(Decimal(str(valeurs[cle] or 0)) * poids for cle, _, poids in parts) / total)


def evaluation_incomplete(inscription, criteres=None):
    """Ce qui manque à l'évaluation finale de l'inscription (libellés), selon la formation."""
    f = inscription.formation
    criteres = list(f.criteres.all()) if criteres is None else criteres
    manques = []
    if criteres and f.poids_projet:
        notes = notes_criteres(inscription)
        if any(c.pk not in notes for c in criteres):
            manques.append("grille du projet")
    if f.poids_soutenance:
        soutenance = getattr(inscription, "soutenance", None)
        if soutenance is None or soutenance.note_sur_20 is None:
            manques.append("soutenance")
    return manques


@transaction.atomic
def enregistrer_notes(inscription, notes):
    """notes : {critere_id: Decimal | None} (None efface la note)."""
    valides = set(inscription.formation.criteres.values_list("pk", flat=True))
    for cid, note in notes.items():
        if cid not in valides:
            continue
        if note is None:
            NoteCritere.objects.filter(inscription=inscription, critere_id=cid).delete()
        else:
            NoteCritere.objects.update_or_create(inscription=inscription, critere_id=cid,
                                                 defaults={"note_sur_20": note})
