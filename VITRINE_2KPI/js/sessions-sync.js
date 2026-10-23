/* 2KPI - Catalogue synchronisé avec la plateforme 2KPI Learn (LEARN_URL, voir js/learn-config.js).
   - chargerSessions(suite)  : sessions ouvertes aux inscriptions (page d'inscription) → SESSIONS ;
   - chargerCatalogue(suite) : formations du catalogue, leur état et leurs sessions → CATALOGUE.
   Sans réponse sous 8 s, la liste reste vide (SESSIONS) ou nulle (CATALOGUE) : la page l'indique. */
function _chargerDepuisLearn(chemin, appliquer, suite) {
  var fini = false;
  function terminer(ok) { if (!fini) { fini = true; suite(ok); } }
  if (typeof LEARN_URL === "undefined" || !window.fetch) { terminer(false); return; }
  var ctrl = window.AbortController ? new AbortController() : null;
  var delai = setTimeout(function () { if (ctrl) ctrl.abort(); terminer(false); }, 8000);
  fetch(LEARN_URL + chemin, { cache: "no-cache", signal: ctrl ? ctrl.signal : undefined })
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(function (data) { clearTimeout(delai); if (!fini) { appliquer(data); terminer(true); } })
    .catch(function () { clearTimeout(delai); terminer(false); });
}

function chargerSessions(suite) {
  _chargerDepuisLearn("/api/sessions/", function (data) {
    SESSIONS.length = 0;
    (data.sessions || []).forEach(function (s) { SESSIONS.push(s); });
  }, suite);
}

function chargerCatalogue(suite) {
  _chargerDepuisLearn("/api/catalogue/", function (data) { CATALOGUE = data.formations || []; }, suite);
}
