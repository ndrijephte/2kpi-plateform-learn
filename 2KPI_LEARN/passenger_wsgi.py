"""Point d'entrée exigé par cPanel « Setup Python App » (Passenger).
Passenger importe la variable `application` depuis ce fichier.
"""
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
