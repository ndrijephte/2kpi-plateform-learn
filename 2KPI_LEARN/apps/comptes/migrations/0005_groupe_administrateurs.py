from django.db import migrations


def rattacher_admins(apps, schema_editor):
    """Les administrateurs existants reçoivent les permissions de l'admin Django."""
    from django.contrib.auth.management import create_permissions
    for app_config in apps.get_app_configs():  # garantit l'existence des permissions
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    Profil = apps.get_model("comptes", "Profil")
    groupe, _ = Group.objects.get_or_create(name="Administrateurs 2KPI")
    groupe.permissions.set(Permission.objects.all())
    for p in Profil.objects.filter(role="admin").select_related("utilisateur"):
        p.utilisateur.groups.add(groupe)
        if not p.utilisateur.is_staff:
            p.utilisateur.is_staff = True
            p.utilisateur.save(update_fields=["is_staff"])


class Migration(migrations.Migration):
    dependencies = [
        ("comptes", "0004_profil_photo"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("agenda", "0004_notifications_envoyees"),
        ("core", "0001_initial"),
        ("evaluation", "0002_alter_presence_unique_together_inscription_promotion_and_more"),
        ("formation", "0003_ressources_tous_formats"),
    ]

    operations = [migrations.RunPython(rattacher_admins, migrations.RunPython.noop)]
