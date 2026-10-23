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
│   ├── realisation-detail.html   (ancienne vue détail : redirige vers realisations.html#id)
│   ├── sessions.html        (catalogue des sessions ouvertes)
│   ├── inscription.html     (formulaire d'inscription à une session)
│   ├── contact.html
│   └── websig-demo.html    (démo cartographique interactive — aussi une réalisation)
├── css/style.css           (feuille de style unique)
├── js/
│   ├── main.js                 (menu mobile, animations, formulaire de contact)
│   ├── sessions-data.js        (vide : aucune session en dur, tout vient de 2KPI Learn)
│   ├── sessions-sync.js        (lecture de /api/catalogue/ et /api/sessions/ sur 2KPI Learn)
│   ├── sessions-catalog.js     (affichage + filtre du catalogue de sessions)
│   ├── inscription.js          (logique de la page d'inscription)
│   ├── inscription-config.js   (adresse de l'API des candidatures de 2KPI Learn)
│   ├── realisations-data.js    (catalogue des réalisations — à éditer pour en ajouter)
│   ├── realisations-catalog.js (affichage + filtre du catalogue de réalisations)
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

## Catalogue des formations & inscription en ligne

**Rien ne se règle dans le site** : formations et sessions se gèrent dans la plateforme 2KPI Learn,
que le site lit en direct (`js/sessions-sync.js`, adresse dans `js/learn-config.js`).

- **Catalogue** (`pages/sessions.html`, menu *Catalogue & sessions*) : toutes les formations cochées
  « Afficher au catalogue du site » (Learn › Paramètres › Formations), lues sur `/api/catalogue/`.
  - Formation dont une session est **ouverte aux inscriptions** : dates, lieu, horaire, places
    restantes (décomptées automatiquement) et bouton **S'inscrire**.
  - Sinon : « Prochaine session bientôt annoncée » et bouton **Être prévenu(e)**, qui déplie un court
    formulaire (nom, e-mail, téléphone, profil étudiant/professionnel, structure) envoyé à
    `/api/interet/`. La personne est prévenue par e-mail, avec le lien d'inscription, dès l'ouverture.
  - Le prix n'apparaît que si l'administration coche « Afficher le prix ».
- **Ouvrir une session** se fait dans Learn : Promotions › *Pilotage* › « Ouvrir les inscriptions ».
  Elle apparaît alors sur le site ; elle en disparaît à la fermeture des inscriptions ou au démarrage.
- **Inscription** (`pages/inscription.html?session=…`) : seules les sessions ouvertes sont proposées ;
  la demande part vers `/api/candidatures/` (traitée dans Learn › *Candidatures*), avec repli sur
  l'e-mail si la plateforme ne répond pas. Sans session ouverte, la page renvoie vers le catalogue.
- Si la plateforme ne répond pas, le catalogue affiche « momentanément indisponible » : le site
  n'affiche jamais de session fictive.

## Réalisations

- Le catalogue (`pages/realisations.html`) est filtrable par catégorie et lit
  `js/realisations-data.js` — **c'est le seul fichier à modifier** pour ajouter une réalisation.
- La cartographie interactive de la Côte d'Ivoire (dossier `ci_websig` de l'ancien site,
  intégré dans `assets/websig-demo/`) est la première réalisation du catalogue : son bouton
  "Ouvrir la carte interactive" renvoie directement vers `pages/websig-demo.html`.
- Les projets sans démo dédiée (Plans d'Urbanisme Directeur, PIDACC/BN, occupation du sol,
  enquêtes socio-démographiques) se lisent **sur la page même** : « Voir le détail » déplie, sous le
  résumé, les chiffres clés et le descriptif renseignés dans `js/realisations-data.js`.
  Lien direct vers un projet ouvert : `pages/realisations.html#<id>` (les anciens liens
  `realisation-detail.html?projet=<id>` y sont redirigés).
- Pour ajouter une future réalisation avec sa propre démo (comme le WebSIG), il suffit de
  déposer la démo dans `assets/`, une page dédiée dans `pages/` si besoin, puis de renseigner
  `vueUrl` dans l'entrée correspondante de `js/realisations-data.js` — sinon, ne rien renseigner
  et le détail se dépliera automatiquement sur la page Réalisations.

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
- **Catalogue & inscription** : catalogue filtrable lu en direct sur 2KPI Learn, liste d'intérêt
  « Être prévenu(e) », inscription reliée aux candidatures de la plateforme (voir ci-dessus).
- **Réalisations paramétrables** : catalogue filtrable, détail dépliable sur place, avec la
  cartographie interactive de la Côte d'Ivoire comme première réalisation (voir ci-dessus).

## Ce qui reste à faire

- **Ouvrir les premières vraies sessions** dans 2KPI Learn (Promotions › Pilotage) : tant qu'aucune
  n'est ouverte, le catalogue propose « Être prévenu(e) » pour chaque formation.
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
