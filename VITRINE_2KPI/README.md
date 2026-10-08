# Site 2KPI — version 2 (légère et autonome)

## Ce que c'est

2KPI est avant tout un centre de formation : le site met en avant le socle télédétection & SIG,
ses quatre domaines d'application (urbanisme, démographie, aménagement paysager, numérique), et
permet de s'inscrire en ligne à une session ouverte. Reconstruction complète sans dépendance
externe lourde : HTML/CSS/JS uniquement, aucune installation ni build nécessaire. Poids total :
**~870 Ko** avec les photos réelles optimisées (hors polices Google Fonts, chargées en ligne et
mises en cache par le navigateur, et hors démo WebSIG qui n'est chargée que si l'utilisateur
visite cette page) contre plus de 150 Mo pour la version précédente.

## Structure

```
VITRINE_2KPI/
├── index.html              (accueil)
├── pages/
│   ├── formations.html
│   ├── academy.html
│   ├── cabinet.html
│   ├── realisations.html         (catalogue des réalisations, filtrable)
│   ├── realisation-detail.html   (vue détail générique — ?projet=id)
│   ├── sessions.html        (catalogue des sessions ouvertes)
│   ├── inscription.html     (formulaire d'inscription à une session)
│   ├── contact.html
│   └── websig-demo.html    (démo cartographique interactive — aussi une réalisation)
├── css/style.css           (feuille de style unique)
├── js/
│   ├── main.js                 (menu mobile, animations, formulaire de contact)
│   ├── sessions-data.js        (catalogue des sessions — à éditer pour les mettre à jour)
│   ├── sessions-catalog.js     (affichage + filtre du catalogue de sessions)
│   ├── inscription.js          (logique de la page d'inscription)
│   ├── inscription-config.js   (URL du Google Sheet — à configurer, voir INSCRIPTIONS-SETUP.md)
│   ├── realisations-data.js    (catalogue des réalisations — à éditer pour en ajouter)
│   ├── realisations-catalog.js (affichage + filtre du catalogue de réalisations)
│   └── realisation-detail.js   (logique de la vue détail générique)
└── assets/
    ├── img/                (logo, favicon, photos réelles optimisées)
    └── websig-demo/        (prototype Leaflet — carte interactive Côte d'Ivoire)
```

## Comment le tester

Double-cliquer sur `index.html` l'ouvre directement dans le navigateur : toutes les pages,
styles et scripts fonctionnent sans serveur (chemins relatifs uniquement).

## Comment le mettre en ligne (aucune compétence technique requise)

Trois options gratuites, sans ligne de commande :

1. **Netlify Drop** (https://app.netlify.com/drop) : glisser-déposer le dossier `VITRINE_2KPI`
   dans la page → un lien public est généré en quelques secondes. Le plus simple pour commencer.
2. **GitHub Pages** : héberger le dossier dans un dépôt GitHub et activer "Pages" dans les
   paramètres du dépôt (gratuit, adresse en `2kpi.github.io` ou domaine personnalisé).
3. **Vercel** : import du dossier via leur interface web, similaire à Netlify.

Ensuite, un nom de domaine (ex. `2kpinnov.org`, déjà utilisé dans les adresses e-mail) peut être
pointé vers l'hébergement choisi.

## Formulaire de contact

Le formulaire ouvre le client mail du visiteur avec le message pré-rempli (fonctionne sans
serveur, mais dépend d'un client mail installé). Pour un envoi silencieux directement depuis le
site (recommandé à terme), brancher un service gratuit comme **Formspree** ou **Web3Forms** :
il suffit d'ajouter une clé dans `js/main.js`, sans changer le design. À faire savoir si utile.

## Sessions de formation & inscription en ligne

- Le catalogue (`pages/sessions.html`) affiche les sessions ouvertes (mode, dates, lieu, places
  restantes, prix) à partir de `js/sessions-data.js` — **c'est le seul fichier à modifier** pour
  ajouter, retirer ou mettre à jour une session (y compris le nombre de places restantes).
- Chaque session renvoie vers `pages/inscription.html?session=...`, qui pré-remplit
  automatiquement le résumé de la session choisie.
- Par défaut, une inscription envoyée ouvre le client mail avec les informations pré-remplies
  (fonctionne tout de suite, sans configuration). Pour que chaque inscription s'ajoute
  automatiquement à un Google Sheet consultable (recommandé), suis les 5 étapes du fichier
  **`INSCRIPTIONS-SETUP.md`** à la racine du site, puis renseigne l'URL obtenue dans
  `js/inscription-config.js`.
- Les places restantes ne se décomptent pas automatiquement (site statique, sans base de
  données) : à mettre à jour toi-même dans `js/sessions-data.js` au fil des inscriptions reçues.

## Réalisations

- Le catalogue (`pages/realisations.html`) est filtrable par catégorie et lit
  `js/realisations-data.js` — **c'est le seul fichier à modifier** pour ajouter une réalisation.
- La cartographie interactive de la Côte d'Ivoire (dossier `ci_websig` de l'ancien site,
  intégré dans `assets/websig-demo/`) est la première réalisation du catalogue : son bouton
  "Ouvrir la carte interactive" renvoie directement vers `pages/websig-demo.html`.
- Les projets sans démo dédiée (Plans d'Urbanisme Directeur, PIDACC/BN, occupation du sol,
  enquêtes socio-démographiques) utilisent une vue détail générique,
  `pages/realisation-detail.html?projet=<id>`, qui affiche automatiquement le résumé, les
  chiffres clés et le descriptif renseignés dans `js/realisations-data.js`.
- Pour ajouter une future réalisation avec sa propre démo (comme le WebSIG), il suffit de
  déposer la démo dans `assets/`, une page dédiée dans `pages/` si besoin, puis de renseigner
  `vueUrl` dans l'entrée correspondante de `js/realisations-data.js` — sinon, ne rien renseigner
  et la vue détail générique s'en charge automatiquement.

## Ce qui a été intégré

- **Positionnement formation-first** : le site met en avant la télédétection & les SIG comme
  socle commun, et l'urbanisme, la démographie, l'aménagement paysager et le numérique comme
  domaines d'application — cohérent avec le document de présentation d'entreprise.
- **Photos réelles** : les illustrations vectorielles ont été remplacées section par section par
  des photos réelles optimisées (56 à 138 Ko chacune, contre 55 à 90 Mo dans les dossiers
  d'origine) : accueil (équipe, galerie terrain/formation/WebSIG/urbanisme/paysager), cabinet
  (photo terrain/drone) et 2KPI Academy (encadrement).
- **Démo WebSIG** : le prototype Leaflet (carte interactive de la Côte d'Ivoire, gestionnaire de
  couches, fonds de carte multiples) est intégré dans `assets/websig-demo/` et accessible via
  `pages/websig-demo.html`, référencé depuis l'accueil, le cabinet, la page formations et,
  désormais, comme première entrée du catalogue de réalisations.
- **Gouvernance** : une section « Équipe & gouvernance » a été ajoutée sur la page Cabinet
  (KOFFI N'Dri Jephté, fondateur géomaticien ; KOPRE Henri Michel, co-fondateur technicien en
  urbanisme et aménagement paysager), avec mention du réseau d'experts mobilisés par domaine
  (démographe, développeurs, formateurs spécialisés).
- **Sessions & inscription** : catalogue filtrable + formulaire d'inscription relié à un Google
  Sheet configurable (voir ci-dessus).
- **Réalisations paramétrables** : catalogue filtrable + vue détail générique, avec la
  cartographie interactive de la Côte d'Ivoire comme première réalisation (voir ci-dessus).

## Ce qui reste à faire

- **Configurer le Google Sheet** : suivre `INSCRIPTIONS-SETUP.md` pour recevoir les inscriptions
  dans un tableur (5 minutes, sans code).
- **Vérifier/ajuster les sessions d'exemple** : dates, lieux, places et prix dans
  `js/sessions-data.js` sont des exemples réalistes à valider ou remplacer par les vraies
  sessions.
- **Ajouter d'autres réalisations** : au fur et à mesure, dans `js/realisations-data.js`.
- **Réseaux sociaux** : les liens WhatsApp/LinkedIn/YouTube/Facebook pointent toujours vers `#`
  en attendant les URLs réelles des comptes 2KPI — à transmettre pour activation en une ligne
  dans chaque page.
- **Nettoyage optionnel** : `assets/websig-demo/assets/img/` contient encore une quinzaine
  d'images héritées de l'ancien site (~50 Mo) qui ne sont plus référencées par aucune page
  (seuls le logo et les 6 vignettes de fonds de carte le sont). Elles n'affectent pas la
  performance du site (jamais chargées par le navigateur) mais peuvent être supprimées
  manuellement pour alléger le dossier sur le disque.
- **Hébergement** : le développement a été fait en local ; le déploiement (Netlify, GitHub
  Pages, Vercel — voir ci-dessus) reste à faire quand tu seras prêt.
