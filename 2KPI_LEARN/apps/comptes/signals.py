from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Profil, Prerequis

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def creer_profil(sender, instance, created, **kwargs):
    if created:
        profil = Profil.objects.create(utilisateur=instance)
        Prerequis.objects.create(profil=profil)
