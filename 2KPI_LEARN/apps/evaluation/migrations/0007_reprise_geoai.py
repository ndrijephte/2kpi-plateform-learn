"""Reprise des prérequis (6 champs fixes du profil) et de la grille de projet (6 critères fixes)
de la formation GéoAI dans les modèles génériques par formation. Rien n'est perdu : les valeurs
de chaque apprenant sont recopiées sur ses inscriptions."""
from django.db import migrations

PREREQUIS = [  # (champ de comptes.Prerequis, libellé)
    ("compte_gee", "Compte Google Earth Engine validé"),
    ("compte_github", "Compte GitHub / GitLab créé"),
    ("miniconda", "Miniconda + JupyterLab installés"),
    ("qgis", "QGIS (version LTR) installé"),
    ("git", "Git installé"),
    ("machine", "Machine ≥ 8 Go RAM, connexion internet"),
]
CRITERES = [  # (champ de EvaluationProjet, libellé, poids %)
    ("acquisition", "Acquisition & prétraitement", 20),
    ("modelisation", "Modélisation ML", 25),
    ("stats_spatiales", "Statistiques spatiales", 15),
    ("alerte", "Système d'alerte", 20),
    ("cartographie", "Cartographie & restitution", 10),
    ("reproductibilite", "Reproductibilité & documentation", 10),
]


def reprendre(apps, schema_editor):
    Formation = apps.get_model("formation", "Formation")
    PrerequisFormation = apps.get_model("formation", "PrerequisFormation")
    CritereEvaluation = apps.get_model("formation", "CritereEvaluation")
    Inscription = apps.get_model("evaluation", "Inscription")
    PrerequisInscription = apps.get_model("evaluation", "PrerequisInscription")
    NoteCritere = apps.get_model("evaluation", "NoteCritere")
    EvaluationProjet = apps.get_model("evaluation", "EvaluationProjet")
    Prerequis = apps.get_model("comptes", "Prerequis")

    # Formations concernées : GéoAI, et toute formation dont un apprenant a des valeurs à reprendre
    renseignes = [p for p in Prerequis.objects.all() if any(getattr(p, c) != "a_faire" for c, _ in PREREQUIS)]
    profils = {p.profil_id: p for p in renseignes}
    ids_prerequis = set(Formation.objects.filter(slug="geoai-sassandra").values_list("pk", flat=True))
    ids_prerequis |= set(Inscription.objects.filter(apprenant__profil__in=profils).values_list("formation_id", flat=True))
    ids_criteres = set(Formation.objects.filter(slug="geoai-sassandra").values_list("pk", flat=True))
    ids_criteres |= set(EvaluationProjet.objects.values_list("inscription__formation_id", flat=True))

    for fid in ids_prerequis:
        definis = {champ: PrerequisFormation.objects.get_or_create(formation_id=fid, libelle=libelle,
                                                                   defaults={"ordre": n})[0]
                   for n, (champ, libelle) in enumerate(PREREQUIS, 1)}
        for insc in Inscription.objects.filter(formation_id=fid, apprenant__profil__in=profils).select_related("apprenant__profil"):
            valeurs = profils[insc.apprenant.profil.pk]
            for champ, pf in definis.items():
                statut = getattr(valeurs, champ)
                if statut != "a_faire":
                    PrerequisInscription.objects.update_or_create(inscription=insc, prerequis=pf,
                                                                  defaults={"statut": statut})

    for fid in ids_criteres:
        definis = {champ: CritereEvaluation.objects.get_or_create(formation_id=fid, libelle=libelle,
                                                                  defaults={"poids": poids, "ordre": n})[0]
                   for n, (champ, libelle, poids) in enumerate(CRITERES, 1)}
        for projet in EvaluationProjet.objects.filter(inscription__formation_id=fid):
            for champ, critere in definis.items():
                note = getattr(projet, champ)
                if note is not None:
                    NoteCritere.objects.update_or_create(inscription_id=projet.inscription_id, critere=critere,
                                                         defaults={"note_sur_20": note})


class Migration(migrations.Migration):
    dependencies = [
        ("evaluation", "0006_grille_prerequis_generiques"),
        ("formation", "0008_grille_prerequis_generiques"),
        ("comptes", "0007_profil_categorie"),
    ]

    operations = [migrations.RunPython(reprendre, migrations.RunPython.noop)]
