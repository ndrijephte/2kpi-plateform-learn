/* 2KPI — Catalogue des sessions de formation : LISTE DE SECOURS
   ===============================================================
   Les sessions se gèrent désormais dans la plateforme 2KPI Learn
   (Promotions › bouton « Vitrine ») : le site les lit en direct via
   js/sessions-sync.js. Ce tableau ne sert que si la plateforme est
   injoignable ; mets-le à jour de temps en temps pour qu'il reste plausible.

   Champs :
   - id            : identifiant unique, sans espace (utilisé dans l'URL ?session=...)
   - titre         : nom de la formation
   - domaine       : "Socle", "Urbanisme", "Démographie", "Paysager" ou "Numérique"
   - mode          : "En ligne", "Présentiel" ou "Hybride"
   - dateAffichage : date lisible affichée sur le site (ex. "Tous les samedis")
   - horaire       : (optionnel) plage horaire, ex. "08h – 16h" (présentiel & hybride)
   - duree         : durée de la session
   - lieu          : lieu (ou "En ligne (visioconférence)")
   - placesTotal   : nombre total de places
   - placesRestantes : nombre de places encore disponibles
   - prix          : prix affiché (FCFA)
   - description   : court résumé affiché sur la carte
*/

var SESSIONS = [
  {
    id: "teledetection-sig-initiation",
    titre: "Télédétection & SIG — Initiation",
    domaine: "Socle",
    mode: "En ligne",
    dateAffichage: "10 août 2026",
    duree: "5 jours",
    lieu: "En ligne (visioconférence)",
    placesTotal: 20,
    placesRestantes: 14,
    prix: "150 000 FCFA",
    description: "Le socle commun à toutes nos formations : fondamentaux QGIS, traitement d'image satellite, cartographie thématique."
  },
  {
    id: "collecte-donnees-terrain",
    titre: "Collecte de données terrain — KoboToolbox & QField",
    domaine: "Socle",
    mode: "Présentiel",
    dateAffichage: "Tous les samedis",
    horaire: "08h – 16h",
    duree: "2 samedis",
    lieu: "Abidjan, Cocody",
    placesTotal: 15,
    placesRestantes: 9,
    prix: "120 000 FCFA",
    description: "Concevoir des questionnaires numériques et fiabiliser la collecte de données sur le terrain."
  },
  {
    id: "urbanisme-numerique",
    titre: "Urbanisme numérique — SIG appliqué à la planification urbaine",
    domaine: "Urbanisme",
    mode: "Présentiel",
    dateAffichage: "Tous les samedis",
    horaire: "08h – 16h",
    duree: "4 samedis",
    lieu: "Abidjan, Cocody",
    placesTotal: 15,
    placesRestantes: 6,
    prix: "180 000 FCFA",
    description: "Mettre la donnée géospatiale au service de la planification urbaine et de la décision territoriale."
  },
  {
    id: "demographie-donnees-spatiales",
    titre: "Démographie & données spatiales",
    domaine: "Démographie",
    mode: "En ligne",
    dateAffichage: "7 septembre 2026",
    duree: "3 jours",
    lieu: "En ligne (visioconférence)",
    placesTotal: 20,
    placesRestantes: 20,
    prix: "150 000 FCFA",
    description: "Analyser les dynamiques de population à partir d'enquêtes de terrain et de la donnée spatiale."
  },
  {
    id: "amenagement-paysager-sig",
    titre: "Aménagement paysager & SIG",
    domaine: "Paysager",
    mode: "Présentiel",
    dateAffichage: "Tous les samedis",
    horaire: "08h – 16h",
    duree: "3 samedis",
    lieu: "Abidjan, Cocody",
    placesTotal: 12,
    placesRestantes: 0,
    prix: "150 000 FCFA",
    description: "Intégrer l'analyse spatiale à la conception d'espaces verts et de trames vertes durables."
  },
  {
    id: "websig-cartographie-interactive",
    titre: "WebSIG & cartographie interactive",
    domaine: "Numérique",
    mode: "Hybride",
    dateAffichage: "Tous les samedis",
    horaire: "08h – 16h",
    duree: "4 samedis",
    lieu: "Abidjan / en ligne",
    placesTotal: 15,
    placesRestantes: 3,
    prix: "160 000 FCFA",
    description: "Passer de la carte statique à des plateformes cartographiques interactives avec Leaflet."
  }
];

function getSessionById(id) {
  for (var i = 0; i < SESSIONS.length; i++) {
    if (SESSIONS[i].id === id) return SESSIONS[i];
  }
  return null;
}
