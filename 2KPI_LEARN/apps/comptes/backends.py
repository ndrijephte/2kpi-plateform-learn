from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class IdentifiantOuEmailBackend(ModelBackend):
    """Connexion avec l'identifiant OU l'adresse e-mail (les apprenants oublient souvent leur identifiant)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username and "@" in username:
            User = get_user_model()
            comptes = list(User._default_manager.filter(email__iexact=username.strip())[:2])
            if len(comptes) == 1:  # adresse partagée par plusieurs comptes : on exige l'identifiant
                username = comptes[0].get_username()
        return super().authenticate(request, username=username, password=password, **kwargs)
