/* 2KPI — Adresse de la plateforme 2KPI Learn (espace apprenant)
   En ligne : learn.2kpinnov.org. Vitrine ouverte en local (localhost / 127.0.0.1) :
   l'app lancée sur le poste (python manage.py runserver). Rien à changer pour déployer. */
var LEARN_LOCAL = /^(localhost|127\.0\.0\.1)$/.test(window.location.hostname);
var LEARN_URL = LEARN_LOCAL ? "http://127.0.0.1:8000" : "https://learn.2kpinnov.org";
