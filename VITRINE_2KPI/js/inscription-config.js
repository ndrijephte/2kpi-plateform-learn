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

var APPS_SCRIPT_URL = "COLLE_ICI_TON_URL_APPS_SCRIPT";

function isAppsScriptConfigured() {
  return APPS_SCRIPT_URL && APPS_SCRIPT_URL.indexOf("https://") === 0;
}
