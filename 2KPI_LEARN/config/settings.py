"""Réglages Django — 2KPI Learn."""
from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("SECRET_KEY", default="dev-insecure-key-change-me")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="127.0.0.1,localhost", cast=Csv())

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Apps 2KPI
    "apps.core",
    "apps.comptes",
    "apps.formation",
    "apps.evaluation",
    "apps.agenda",
    "apps.tableau_bord",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.interface",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Base de données : PostgreSQL (local + prod) ; SQLite uniquement si DB_ENGINE est vide
if config("DB_ENGINE", default="") == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME"),
            "USER": config("DB_USER"),
            "PASSWORD": config("DB_PASSWORD"),
            "HOST": config("DB_HOST", default="127.0.0.1"),
            "PORT": config("DB_PORT", default="5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr"
TIME_ZONE = "Africa/Abidjan"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# En développement (DEBUG), on évite le stockage "manifest" (pas besoin de
# collectstatic) ; en production WhiteNoise sert les statiques compressés+manifest.
if DEBUG:
    STORAGES["staticfiles"]["BACKEND"] = "django.contrib.staticfiles.storage.StaticFilesStorage"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"          # public : logo, image de connexion, photos de profil
PRIVATE_ROOT = BASE_DIR / "prive"        # privé : ressources et livrables (servis via contrôle d'accès)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_REDIRECT_URL = "tableau_bord:accueil"
LOGOUT_REDIRECT_URL = "login"
LOGIN_URL = "login"

# Sécurité (activée hors DEBUG)
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())
if not DEBUG:
    SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 2592000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    X_FRAME_OPTIONS = "DENY"
    if config("BEHIND_PROXY", default=False, cast=bool):  # HTTPS terminé par un proxy frontal
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Site vitrine autorisé à appeler l'API publique (candidatures)
VITRINE_ORIGINS = config("VITRINE_ORIGINS", default="https://2kpinnov.org,https://www.2kpinnov.org", cast=Csv())

# E-mail : SMTP de l'hébergeur (465 = SSL, 587 = STARTTLS). Vide = e-mails affichés dans la console.
EMAIL_HOST = config("EMAIL_HOST", default="")
if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_PORT = config("EMAIL_PORT", default=465, cast=int)
    EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
    EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
    EMAIL_USE_SSL = config("EMAIL_USE_SSL", default=EMAIL_PORT == 465, cast=bool)
    EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=not EMAIL_USE_SSL, cast=bool)
    EMAIL_TIMEOUT = 15
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="2KPI Learn <no-reply@2kpinnov.org>")
SERVER_EMAIL = config("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)
# ADMINS=Nom <adresse>,Autre <adresse> : reçoivent le détail des erreurs 500 en production
ADMINS = [(n.split("<")[0].strip(), n.split("<")[1].rstrip("> ").strip())
          for n in config("ADMINS", default="", cast=Csv()) if "<" in n]

# Journaux : logs/2kpi_learn.log (rotation 5 × 2 Mo) + e-mail aux ADMINS sur erreur serveur
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "{asctime} {levelname} {name} — {message}", "style": "{"}},
    "filters": {"prod": {"()": "django.utils.log.RequireDebugFalse"}},
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
        "fichier": {"class": "logging.handlers.RotatingFileHandler", "filename": LOG_DIR / "2kpi_learn.log",
                    "maxBytes": 2 * 1024 * 1024, "backupCount": 5, "encoding": "utf-8", "formatter": "simple"},
        "mail_admins": {"class": "django.utils.log.AdminEmailHandler", "filters": ["prod"], "level": "ERROR"},
    },
    "loggers": {
        "django": {"handlers": ["console", "fichier"], "level": "INFO"},
        "django.request": {"handlers": ["fichier", "mail_admins"], "level": "ERROR", "propagate": False},
        "apps": {"handlers": ["console", "fichier"], "level": "INFO"},
    },
}
