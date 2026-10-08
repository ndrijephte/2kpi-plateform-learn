/* 2KPI — Catalogue synchronisé avec la plateforme 2KPI Learn
   Les sessions publiées sont gérées dans l'app (Promotions › Vitrine) et lues ici via
   LEARN_URL/api/sessions/ : dates, lieu, prix et places restantes toujours à jour.
   Si l'app ne répond pas (5 s), on garde la liste de secours de js/sessions-data.js. */
function chargerSessions(suite) {
  var fini = false;
  function terminer() { if (!fini) { fini = true; suite(); } }
  if (typeof LEARN_URL === "undefined" || !window.fetch) { terminer(); return; }

  var ctrl = window.AbortController ? new AbortController() : null;
  var delai = setTimeout(function () { if (ctrl) ctrl.abort(); terminer(); }, 5000);
  fetch(LEARN_URL + "/api/sessions/", { cache: "no-cache", signal: ctrl ? ctrl.signal : undefined })
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(function (data) {
      if (fini || !data || !Array.isArray(data.sessions)) return;
      SESSIONS.length = 0;
      data.sessions.forEach(function (s) { SESSIONS.push(s); });
    })
    .catch(function () { /* liste de secours */ })
    .then(function () { clearTimeout(delai); terminer(); });
}
