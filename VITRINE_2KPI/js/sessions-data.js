/* 2KPI - Sessions de formation
   =============================
   Aucune session n'est écrite en dur dans le site : formations et sessions se gèrent dans la
   plateforme 2KPI Learn, et le site les lit en direct (js/sessions-sync.js) :
   - catalogue des formations : Paramètres › Formations › « Afficher au catalogue du site » ;
   - session réservable : Promotions › Pilotage › « Ouvrir les inscriptions ».
   Si la plateforme ne répond pas, le site affiche un message d'indisponibilité plutôt que des
   sessions fictives. */
var SESSIONS = [];
var CATALOGUE = null;
