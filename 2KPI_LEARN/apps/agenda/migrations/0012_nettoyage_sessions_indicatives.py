"""Catalogue des formations et nettoyage des sessions indicatives du site vitrine.

1. Les 6 formations annoncées jusqu'ici sur le site (liste écrite en dur) entrent au catalogue :
   créées si elles n'existent pas, complétées sinon (domaine, mode, durée, résumé).
2. Les promotions « vitrine » qui n'étaient que des fiches indicatives (aucun apprenant, aucune séance
   datée, aucun formateur, aucun exercice) sont retirées : leur formation reste au catalogue, et les
   vraies sessions se créeront selon le workflow (Promotions › Pilotage › Ouvrir les inscriptions).
   Une promotion vers laquelle pointe une candidature est archivée plutôt que supprimée.
"""
from django.db import migrations
from django.utils.text import slugify

OFFRES = [
    ("Télédétection & SIG - Initiation", "Socle", "En ligne", "5 jours",
     "Le socle commun à toutes nos formations : fondamentaux QGIS, traitement d'image satellite, cartographie thématique."),
    ("Collecte de données terrain - KoboToolbox & QField", "Socle", "Présentiel", "2 samedis",
     "Concevoir des questionnaires numériques et fiabiliser la collecte de données sur le terrain."),
    ("Urbanisme numérique - SIG appliqué à la planification urbaine", "Urbanisme", "Présentiel", "4 samedis",
     "Mettre la donnée géospatiale au service de la planification urbaine et de la décision territoriale."),
    ("Démographie & données spatiales", "Démographie", "En ligne", "3 jours",
     "Analyser les dynamiques de population à partir d'enquêtes de terrain et de la donnée spatiale."),
    ("Aménagement paysager & SIG", "Paysager", "Présentiel", "3 samedis",
     "Intégrer l'analyse spatiale à la conception d'espaces verts et de trames vertes durables."),
    ("WebSIG & cartographie interactive", "Numérique", "Hybride", "4 samedis",
     "Passer de la carte statique à des plateformes cartographiques interactives avec Leaflet."),
]


def nettoyer(apps, schema_editor):
    Formation = apps.get_model("formation", "Formation")
    Promotion = apps.get_model("agenda", "Promotion")
    Candidature = apps.get_model("comptes", "Candidature")
    JournalStatut = apps.get_model("evaluation", "JournalStatut")

    for titre, domaine, mode, duree, resume in OFFRES:
        f = (Formation.objects.filter(slug=slugify(titre)).first()
             or Formation.objects.filter(titre__iexact=titre).first())
        if f is None:
            f = Formation(titre=titre, slug=slugify(titre), description=resume)
        f.catalogue, f.domaine, f.mode = True, domaine, mode
        f.duree_type = f.duree_type or duree
        f.resume = f.resume or resume
        f.save()

    indicatives = (Promotion.objects.filter(publiee_vitrine=True) | Promotion.objects.filter(statut="inscriptions"))
    for p in indicatives.distinct():
        if (p.inscriptions.exists() or p.evenements.exists() or p.affectations.exists() or p.formateur_id
                or p.exercices.exists()):
            continue  # une vraie session : on n'y touche pas
        f = p.formation
        f.catalogue = True
        f.domaine, f.mode = p.domaine or f.domaine, p.mode or f.mode
        f.duree_type = f.duree_type or p.duree
        f.resume = f.resume or p.description_vitrine
        f.prix_indicatif = f.prix_indicatif or p.prix
        f.save()
        if Candidature.objects.filter(promotion=p).exists():
            de = p.statut
            p.statut, p.active, p.publiee_vitrine = "archivee", False, False
            p.save(update_fields=["statut", "active", "publiee_vitrine"])
            JournalStatut.objects.create(promotion=p, de=de, vers="archivee",
                                         motif="Session indicative du site retirée (la formation reste au catalogue)")
        else:
            p.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("agenda", "0011_prix_optionnel_vitrine"),
        ("formation", "0009_catalogue_formations"),
        ("comptes", "0009_catalogue_formations"),
        ("evaluation", "0009_attestations"),
        ("exercices", "0001_initial"),
    ]

    operations = [migrations.RunPython(nettoyer, migrations.RunPython.noop)]
