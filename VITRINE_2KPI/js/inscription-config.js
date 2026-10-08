/* 2KPI — Configuration du dispositif d'inscription
   ==================================================
   Par défaut, le formulaire d'inscription fonctionne déjà : il ouvre le
   client mail avec les informations pré-remplies (comme le formulaire de
   contact). C'est fonctionnel tout de suite, mais chaque inscription arrive
   séparément par e-mail, sans liste centralisée.

   Pour que chaque inscription s'ajoute AUTOMATIQUEMENT à un Google Sheet
   (recommandé pour suivre le remplissage des sessions), suis les 5 étapes du
   fichier INSCRIPTIONS-SETUP.md à la racine du site, puis colle ici l'URL
   de déploiement obtenue à la dernière étape, à la place de la valeur
   ci-dessous. Le site basculera alors automatiquement sur le Google Sheet,
   sans autre modification. */

/* Plateforme 2KPI Learn (recommandé) : chaque inscription arrive dans
   learn.2kpinnov.org › Candidatures. L'admin l'accepte en un clic : le compte
   apprenant est créé et la personne reçoit un e-mail pour activer son accès.
   Laisser vide pour revenir au Google Sheet / à l'e-mail. */
var LEARN_API_URL = LEARN_URL + "/api/candidatures/";  /* LEARN_URL : js/learn-config.js */

var APPS_SCRIPT_URL = "COLLE_ICI_TON_URL_APPS_SCRIPT";

function isLearnConfigured() {
  return !!LEARN_API_URL && (LEARN_API_URL.indexOf("https://") === 0 || LEARN_LOCAL);
}

function isAppsScriptConfigured() {
  return APPS_SCRIPT_URL && APPS_SCRIPT_URL.indexOf("https://") === 0;
}
