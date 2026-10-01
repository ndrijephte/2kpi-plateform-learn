"""Stockage privé : fichiers jamais servis directement par le serveur web.
Ils ne sont délivrés que par des vues Django qui vérifient les droits (ressources, livrables)."""
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.functional import cached_property


class StockagePrive(FileSystemStorage):
    """Comme FileSystemStorage, mais enraciné dans PRIVATE_ROOT (lu dynamiquement)."""

    @cached_property
    def base_location(self):
        return self._value_or_setting(self._location, settings.PRIVATE_ROOT)

    def _clear_cached_properties(self, setting, **kwargs):
        super()._clear_cached_properties(setting, **kwargs)
        if setting == "PRIVATE_ROOT":
            self.__dict__.pop("base_location", None)
            self.__dict__.pop("location", None)

    def url(self, name):  # garde-fou : aucune URL publique pour ces fichiers
        raise ValueError("Fichier privé : utiliser la vue de téléchargement contrôlée.")


_stockage = StockagePrive()


def stockage_prive():
    return _stockage
