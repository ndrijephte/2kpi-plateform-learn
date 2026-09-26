from .models import Inscription

def inscription_courante(user):
    return Inscription.objects.filter(apprenant=user).order_by("-id").first()
