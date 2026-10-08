/* 2KPI — Catalogue des réalisations
   ===================================
   C'est ICI que tu ajoutes une nouvelle réalisation : ajoute un objet dans
   le tableau REALISATIONS ci-dessous. La page réalisations.html (liste et
   filtres) et la page de détail générique (realisation-detail.html) lisent
   automatiquement ce fichier — aucune autre page à modifier.

   Champs :
   - id          : identifiant unique, sans espace (utilisé dans l'URL ?projet=...)
   - titre       : nom du projet
   - categorie   : "WebSIG", "Urbanisme", "Climat & adaptation", "Environnement"
                   ou "Démographie" (sert aussi de filtre)
   - annee       : année ou période affichée
   - resume      : court résumé affiché sur la carte
   - details     : liste de paragraphes affichés sur la vue détail (utilisé
                   seulement si le projet n'a pas de démo dédiée — voir vueUrl)
   - chiffres    : (optionnel) liste de { valeur, label } mise en avant sur la vue détail
   - vueUrl      : (optionnel) si renseigné, le bouton "Voir la réalisation" ouvre
                   directement cette page (ex. une démo interactive dédiée) au lieu
                   de la vue détail générique
   - vueLabel    : (optionnel) texte du bouton si vueUrl est renseigné
*/

var REALISATIONS = [
  {
    id: "websig-cote-divoire",
    titre: "Cartographie interactive de la Côte d'Ivoire (WebSIG)",
    categorie: "WebSIG",
    annee: "2026",
    resume: "Prototype de carte interactive développé avec Leaflet : bascule de fonds de carte, gestionnaire de couches, et découpage administratif par département.",
    details: [
      "Ce projet illustre concrètement ce qu'est le WebSIG appliqué à un territoire réel : une carte interactive de la Côte d'Ivoire, avec plusieurs fonds de carte (OSM, satellite, relief), un gestionnaire de couches et l'affichage des limites administratives et des départements.",
      "C'est ce type d'outil — de la donnée géospatiale brute à une plateforme cartographique accessible en ligne — que la formation WebSIG & cartographie interactive de 2KPI permet de construire."
    ],
    vueUrl: "websig-demo.html",
    vueLabel: "Ouvrir la carte interactive"
  },
  {
    id: "pud-80-chefs-lieux",
    titre: "Plans d'Urbanisme Directeur (PUD) — 80 chefs-lieux de département",
    categorie: "Urbanisme",
    annee: "2024",
    resume: "Élaboration de plans d'urbanisme directeur pour des chefs-lieux de département, incluant cartographie, questionnaires numériques et validation des données spatiales avant traitement SIG.",
    details: [
      "Projet mené pour le Ministère de la Construction, du Logement et de l'Urbanisme (MCLU) : conception et implémentation de questionnaires numériques (XLSForm, KoboToolbox) adaptés aux enquêtes de terrain, paramétrage de tablettes pour la collecte, et mise à jour des plans d'état des lieux.",
      "Contribution à la planification et au suivi des missions de terrain sur l'ensemble des 80 chefs-lieux de département couverts par le programme."
    ],
    chiffres: [{ valeur: "80+", label: "chefs-lieux couverts" }]
  },
  {
    id: "pidacc-bn",
    titre: "Plans communautaires d'adaptation au changement climatique (PIDACC/BN)",
    categorie: "Climat & adaptation",
    annee: "2024",
    resume: "Collecte et analyse de données sur plusieurs départements dans le cadre d'un programme régional du bassin du fleuve Niger : diagnostics territoriaux et cartes d'occupation du sol.",
    details: [
      "Réalisation de sept plans communautaires d'adaptation au changement climatique dans la portion nationale du bassin du fleuve Niger, pour le compte du groupement ANGE-PU/BURGEAP/Groupe EFORT.",
      "Planification des missions de collecte sur 7 départements, conception de questionnaires numériques sous QField, puis traitement d'images satellites Landsat pour la réalisation de cartes d'occupation du sol (dynamiques spatio-temporelles 1986-2020)."
    ],
    chiffres: [{ valeur: "7", label: "plans communautaires réalisés" }]
  },
  {
    id: "occupation-sol-zones-humides",
    titre: "Occupation du sol & zones humides",
    categorie: "Environnement",
    annee: "2019 – 2022",
    resume: "Traitement d'images satellites (Sentinel-2, Landsat) pour la caractérisation de ressources naturelles et le suivi de dynamiques spatio-temporelles sur plusieurs décennies.",
    details: [
      "Travaux menés notamment sur le site Ramsar d'Azagny (Sud de la Côte d'Ivoire) et le site de N'ganda N'ganda : caractérisation des ressources naturelles végétales en zone humide, évaluation des impacts des pressions agricoles, et étude comparative de capteurs satellites (Sentinel-2 / Landsat-8 OLI).",
      "Ces travaux ont donné lieu à plusieurs publications scientifiques — voir la section Publications ci-dessous."
    ]
  },
  {
    id: "etudes-enquetes-socio-demo",
    titre: "Études d'impact et enquêtes socio-démographiques",
    categorie: "Démographie",
    annee: "2020 – 2024",
    resume: "Conception de questionnaires numériques, encadrement d'agents de collecte, contrôle qualité et analyse statistique pour des études d'impact environnemental et des évaluations de programmes.",
    details: [
      "Missions menées pour l'UNICEF (évaluation du programme ENACTE, Nawa) et l'UNFPA (enquête nationale sur la disponibilité des produits et services de santé reproductive), incluant coordination du dénombrement, cartographie des ménages et administration de questionnaires numériques (CSPro, KoboCollect).",
      "Contrôle qualité rigoureux des données collectées et appui technique aux équipes d'enquêteurs sur le terrain."
    ],
    chiffres: [{ valeur: "400+", label: "points de collecte géoréférencés" }]
  }
];

function getRealisationById(id) {
  for (var i = 0; i < REALISATIONS.length; i++) {
    if (REALISATIONS[i].id === id) return REALISATIONS[i];
  }
  return null;
}
