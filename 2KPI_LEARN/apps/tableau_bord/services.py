"""Calculs de synthèse — reproduit l'onglet Tableau_de_bord du classeur de suivi."""
from decimal import Decimal
from apps.formation.models import Seance, Competence
from apps.evaluation.models import Presence, Livrable, EvaluationCompetence


def synthese(inscription):
    formation = inscription.formation
    total_seances = Seance.objects.filter(module__formation=formation).count()
    total_competences = Competence.objects.filter(module__formation=formation).count()

    presences = Presence.objects.filter(inscription=inscription)
    presents = presences.filter(statut=Presence.Statut.PRESENT).count()
    taux_presence = round(100 * presents / total_seances) if total_seances else 0

    livrables = Livrable.objects.filter(inscription=inscription, note_sur_20__isnull=False)
    notes = [float(l.note_sur_20) for l in livrables]
    moyenne_seances = round(sum(notes) / len(notes), 2) if notes else 0.0

    evals = EvaluationCompetence.objects.filter(inscription=inscription)
    competences_validees = evals.filter(valide=True).count()
    niveaux = [e.eval_formateur for e in evals if e.eval_formateur]
    niveau_moyen = round(sum(niveaux) / len(niveaux), 1) if niveaux else 0.0

    note_projet = float(getattr(getattr(inscription, "projet", None), "note_sur_20", 0) or 0)
    note_soutenance = float(getattr(getattr(inscription, "soutenance", None), "note_sur_20", 0) or 0)

    # Note globale = 40% continu + 40% projet + 20% soutenance
    note_globale = round(0.40 * moyenne_seances + 0.40 * note_projet + 0.20 * note_soutenance, 2)

    # Progression = part des séances avec livrable rendu
    rendus = Livrable.objects.filter(inscription=inscription, rendu=True).count()
    progression = round(100 * rendus / total_seances) if total_seances else 0

    return {
        "taux_presence": taux_presence,
        "moyenne_seances": moyenne_seances,
        "competences_validees": competences_validees,
        "total_competences": total_competences,
        "niveau_moyen": niveau_moyen,
        "note_projet": note_projet,
        "note_soutenance": note_soutenance,
        "note_globale": note_globale,
        "progression": progression,
    }
