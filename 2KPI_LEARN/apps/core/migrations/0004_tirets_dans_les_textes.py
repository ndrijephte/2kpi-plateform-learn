"""Charte typographique : le tiret long « — » qui relie deux textes devient « - » dans les contenus
déjà enregistrés (titres de formations, promotions, quiz…), comme dans le code de l'application."""
from django.db import migrations, models

APPS = ("formation", "agenda", "evaluation", "core", "comptes")


def remplacer(apps, schema_editor):
    for app in APPS:
        for modele in apps.get_app_config(app).get_models():
            champs = [f.name for f in modele._meta.fields
                      if isinstance(f, (models.CharField, models.TextField))
                      and not isinstance(f, (models.SlugField, models.EmailField, models.URLField))]
            for champ in champs:
                for obj in modele.objects.filter(**{f"{champ}__contains": " — "}).only("pk", champ):
                    setattr(obj, champ, getattr(obj, champ).replace(" — ", " - "))
                    obj.save(update_fields=[champ])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0003_attestations"),
        ("formation", "0008_grille_prerequis_generiques"),
        ("agenda", "0011_prix_optionnel_vitrine"),
        ("evaluation", "0009_attestations"),
        ("comptes", "0008_retrait_modeles_geoai"),
    ]

    operations = [migrations.RunPython(remplacer, migrations.RunPython.noop)]
