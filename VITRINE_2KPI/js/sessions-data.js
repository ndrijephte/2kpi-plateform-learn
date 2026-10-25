/* 2KPI - Sessions de formation
   =============================
   Aucune session n'est écrite en dur dans le site : formations et sessions se gèrent dans la
   plateforme 2KPI Learn, et le site les lit en direct (js/sessions-sync.js) :
   - catalogue des formations : Paramètres › Formations › « Afficher au catalogue du site » ;
   - session réservable : Sessions › « Lancer une session » puis « Publier ».
   Si la plateforme ne répond pas, le site affiche un message d'indisponibilité plutôt que des
   sessions fictives. */
var SESSIONS = [];
var CATALOGUE = null;

/* Session ouverte d'après son identifiant public (paramètre ?session= de la page d'inscription) */
function getSessionById(id) {
  for (var i = 0; i < SESSIONS.length; i++) {
    if (SESSIONS[i].id === id) return SESSIONS[i];
  }
  return null;
}
