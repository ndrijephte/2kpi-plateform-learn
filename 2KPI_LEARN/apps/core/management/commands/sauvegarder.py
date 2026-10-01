"""Sauvegarde quotidienne : base de données + fichiers (media/, prive/), avec rotation.

    python manage.py sauvegarder              # dans BASE_DIR/sauvegardes, conserve 14 jours
    python manage.py sauvegarder --garder 30 --dossier /home/compte/sauvegardes

À programmer en cron (cPanel › Tâches cron), une fois par nuit.
"""
import datetime as dt
import gzip
import os
import shutil
import subprocess
import tarfile
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Sauvegarde la base et les fichiers déposés, puis supprime les sauvegardes anciennes."

    def add_arguments(self, parser):
        parser.add_argument("--dossier", default=str(settings.BASE_DIR / "sauvegardes"))
        parser.add_argument("--garder", type=int, default=14, help="Nombre de jours conservés.")

    def handle(self, dossier, garder, **options):
        cible = Path(dossier)
        cible.mkdir(parents=True, exist_ok=True)
        horodatage = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
        db = settings.DATABASES["default"]

        # 1. Base de données
        if "postgresql" in db["ENGINE"]:
            fichier = cible / f"base_{horodatage}.sql.gz"
            env = {**os.environ, "PGPASSWORD": str(db.get("PASSWORD", ""))}
            cmd = ["pg_dump", "--no-owner", "--no-privileges", "-h", str(db.get("HOST") or "localhost"),
                   "-p", str(db.get("PORT") or 5432), "-U", str(db["USER"]), str(db["NAME"])]
            try:
                dump = subprocess.run(cmd, env=env, check=True, capture_output=True).stdout
            except FileNotFoundError:
                raise CommandError("pg_dump introuvable sur ce serveur.")
            except subprocess.CalledProcessError as e:
                raise CommandError(f"pg_dump a échoué : {e.stderr.decode(errors='ignore')}")
            with gzip.open(fichier, "wb") as f:
                f.write(dump)
        else:
            fichier = cible / f"base_{horodatage}.sqlite3"
            shutil.copy2(db["NAME"], fichier)
        self.stdout.write(f"Base → {fichier.name}")

        # 2. Fichiers déposés (publics et privés)
        archive = cible / f"fichiers_{horodatage}.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            for racine, nom in ((settings.MEDIA_ROOT, "media"), (settings.PRIVATE_ROOT, "prive")):
                if Path(racine).exists():
                    tar.add(racine, arcname=nom)
        self.stdout.write(f"Fichiers → {archive.name}")

        # 3. Rotation
        limite = dt.datetime.now() - dt.timedelta(days=garder)
        supprimes = 0
        for f in cible.glob("*_*"):
            if f.is_file() and dt.datetime.fromtimestamp(f.stat().st_mtime) < limite:
                f.unlink()
                supprimes += 1
        self.stdout.write(self.style.SUCCESS(f"Sauvegarde terminée ({supprimes} ancienne(s) supprimée(s))."))
