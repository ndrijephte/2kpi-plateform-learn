import datetime as dt
from django.db import migrations, models

# Ancien rythme figé -> créneaux paramétrables
ANCIEN = {
    "lundi": (0, dt.time(21, 30), "en_ligne"),
    "mercredi": (2, dt.time(21, 30), "en_ligne"),
    "vendredi": (4, dt.time(21, 30), "en_ligne"),
    "samedi": (5, dt.time(8, 0), "hybride"),
}


def convertir(apps, schema_editor):
    Seance = apps.get_model("formation", "Seance")
    for s in Seance.objects.select_related("module"):
        jour, heure, mode = ANCIEN.get(s.jour, (0, dt.time(21, 30), "en_ligne"))
        s.jour_num, s.heure_debut, s.mode, s.semaine = jour, heure, mode, s.module.ordre or 1
        s.save(update_fields=["jour_num", "heure_debut", "mode", "semaine"])


def revenir(apps, schema_editor):
    Seance = apps.get_model("formation", "Seance")
    inverse = {v[0]: k for k, v in ANCIEN.items()}
    for s in Seance.objects.all():
        s.jour = inverse.get(s.jour_num, "lundi")
        s.save(update_fields=["jour"])


class Migration(migrations.Migration):
    dependencies = [("formation", "0001_initial")]

    operations = [
        migrations.AddField("seance", "jour_num", models.PositiveSmallIntegerField(default=0)),
        migrations.AddField("seance", "heure_debut", models.TimeField("Heure de début", default=dt.time(21, 30))),
        migrations.AddField("seance", "mode", models.CharField(max_length=12, default="en_ligne", choices=[
            ("presentiel", "Présentiel"), ("en_ligne", "En ligne"), ("hybride", "Hybride")])),
        migrations.AddField("seance", "semaine", models.PositiveSmallIntegerField(
            null=True, blank=True,
            help_text="Semaine de la formation (1 = semaine de démarrage). Vide = numéro d'ordre du module.")),
        migrations.AddField("seance", "lieu", models.CharField(max_length=200, blank=True)),
        migrations.AddField("seance", "objectifs", models.TextField("Objectifs & déroulé", blank=True)),
        migrations.RunPython(convertir, revenir),
        migrations.RemoveField("seance", "jour"),
        migrations.RenameField("seance", "jour_num", "jour"),
        migrations.AlterField("seance", "jour", models.PositiveSmallIntegerField(default=0, choices=[
            (0, "Lundi"), (1, "Mardi"), (2, "Mercredi"), (3, "Jeudi"),
            (4, "Vendredi"), (5, "Samedi"), (6, "Dimanche")])),
        migrations.AlterField("seance", "theme", models.CharField("Titre / thème", max_length=250, blank=True)),
        migrations.AlterField("seance", "duree_prevue_h", models.DecimalField(
            "Durée (h)", max_digits=4, decimal_places=1, default=1.5)),
    ]
