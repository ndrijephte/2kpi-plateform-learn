# Faire arriver les inscriptions dans un Google Sheet

> **Mise à jour :** par défaut, les inscriptions sont désormais envoyées à la plateforme
> **2KPI Learn** (`learn.2kpinnov.org` › Candidatures), où l'admin les accepte en un clic :
> le compte apprenant est créé et un e-mail d'activation est envoyé. Réglage :
> `LEARN_API_URL` dans `js/inscription-config.js`. Le Google Sheet ci-dessous ne sert que si
> `LEARN_API_URL` est vidé ; l'e-mail reste le repli automatique si la plateforme est injoignable.

Par défaut, le formulaire d'inscription (`pages/inscription.html`) fonctionne déjà :
chaque inscription ouvre le client mail avec les informations pré-remplies, comme le
formulaire de contact. C'est utilisable tout de suite, mais chaque inscription arrive
séparément par e-mail, sans liste centralisée.

Pour que chaque inscription s'ajoute **automatiquement à un Google Sheet** que tu peux
consulter et trier à tout moment (nom, session, date, places), suis ces 5 étapes. Aucune
compétence technique particulière n'est nécessaire — copier/coller suffit.

## 1. Créer le Google Sheet

1. Va sur [sheets.google.com](https://sheets.google.com) et crée une feuille vide.
2. Renomme-la, par exemple **« 2KPI — Inscriptions »**.

## 2. Ouvrir l'éditeur de script

Dans le Google Sheet : menu **Extensions > Apps Script**. Une nouvelle page s'ouvre avec
un éditeur de code.

## 3. Coller le script

Supprime le contenu par défaut (`function myFunction() {...}`) et colle exactement ceci :

```javascript
function doPost(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  var data = JSON.parse(e.postData.contents);

  if (sheet.getLastRow() === 0) {
    sheet.appendRow(["Horodatage", "Session", "Nom", "Email", "Téléphone", "Participants", "Message"]);
  }

  sheet.appendRow([
    new Date(),
    data.session || "",
    data.nom || "",
    data.email || "",
    data.telephone || "",
    data.participants || "",
    data.message || ""
  ]);

  return ContentService
    .createTextOutput(JSON.stringify({ result: "success" }))
    .setMimeType(ContentService.MimeType.JSON);
}
```

Clique sur l'icône disquette (Enregistrer le projet). Donne-lui un nom si demandé, par
exemple « Inscriptions 2KPI ».

## 4. Déployer comme application web

1. Clique sur **Déployer > Nouveau déploiement** (en haut à droite).
2. Type de déploiement : **Application Web**.
3. « Exécuter en tant que » : **Moi** (ton compte Google).
4. « Qui a accès » : **Tout le monde**.
5. Clique sur **Déployer**. Google peut demander d'autoriser le script à accéder à ta
   feuille : accepte (c'est ton propre script, sur ta propre feuille).
6. Copie l'**URL de l'application Web** affichée (elle ressemble à
   `https://script.google.com/macros/s/AKfycb.../exec`).

## 5. Coller l'URL dans le site

Ouvre le fichier `js/inscription-config.js` et remplace :

```javascript
var APPS_SCRIPT_URL = "COLLE_ICI_TON_URL_APPS_SCRIPT";
```

par :

```javascript
var APPS_SCRIPT_URL = "https://script.google.com/macros/s/TON_ID/exec";
```

Enregistre. C'est tout : dès qu'un visiteur s'inscrit sur `pages/inscription.html`, une
ligne s'ajoute automatiquement dans ton Google Sheet, avec la session, son nom, son email,
son téléphone, le nombre de participants et son message.

## Suivi des places disponibles

Le nombre de places restantes affiché sur le site (`js/sessions-data.js`, champ
`placesRestantes`) n'est **pas automatique** : le site est statique (sans base de données),
donc c'est toi qui mets à jour ce chiffre à la main, en t'appuyant sur ton Google Sheet,
chaque fois qu'une inscription est confirmée. C'est le compromis le plus simple pour rester
sans back-office ni hébergement complexe. Si tu veux plus tard un comptage 100% automatique,
il faudra une petite API (étape supplémentaire, à envisager quand le volume d'inscriptions
le justifiera).

## Test rapide

Une fois configuré, ouvre `pages/inscription.html` en local, remplis le formulaire avec de
fausses données et envoie-le. Une nouvelle ligne doit apparaître dans le Google Sheet en
quelques secondes (pas de message de confirmation détaillé dans le navigateur, c'est normal :
la technique utilisée ne permet pas de lire la réponse, mais l'écriture fonctionne).
