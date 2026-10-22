"""L'administrateur n'est ni apprenant ni formateur : un super-utilisateur a le rôle « admin », et aucun
administrateur n'est référent ni affecté à une promotion (il pilote tout sans cela)."""
from django.db import migrations
from django.db.models import Q


def separer_admin(apps, schema_editor):
    Profil = apps.get_model("comptes", "Profil")
    Promotion = apps.get_model("agenda", "Promotion")
    Affectation = apps.get_model("agenda", "Affectation")
    Profil.objects.filter(utilisateur__is_superuser=True).exclude(role="admin").update(role="admin")
    admins = Q(is_superuser=True) | Q(profil__role="admin")
    User = Profil._meta.get_field("utilisateur").related_model
    ids = list(User.objects.filter(admins).values_list("pk", flat=True))
    Promotion.objects.filter(formateur_id__in=ids).update(formateur=None)
    Affectation.objects.filter(formateur_id__in=ids).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("agenda", "0008_affectations_formateurs"),
        ("comptes", "0007_profil_categorie"),
    ]

    operations = [migrations.RunPython(separer_admin, migrations.RunPython.noop)]
