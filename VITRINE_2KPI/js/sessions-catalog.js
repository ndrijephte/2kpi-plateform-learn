/* 2KPI — Rendu du catalogue de sessions (pages/sessions.html)
   Charge les sessions publiées dans 2KPI Learn (js/sessions-sync.js, repli
   sur js/sessions-data.js) et affiche les cartes, avec filtre par domaine. */
(function () {
  "use strict";

  var container = document.getElementById("sessions-list");
  if (!container) return;

  var filterBar = document.getElementById("session-filters");
  var domaines = ["Tous", "Socle", "Urbanisme", "Démographie", "Paysager", "Numérique"];
  var current = "Tous";

  var ICON_CAL = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 10h18"/></svg>';
  var ICON_CLOCK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>';
  var ICON_PIN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 22s7-7.4 7-12a7 7 0 1 0-14 0c0 4.6 7 12 7 12Z"/><circle cx="12" cy="10" r="2.5"/></svg>';
  var ICON_ARROW = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M13 6l6 6-6 6"/></svg>';

  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function renderCard(s) {
    var full = s.placesRestantes <= 0;
    var pct = s.placesTotal ? Math.max(0, Math.min(100, Math.round((s.placesRestantes / s.placesTotal) * 100))) : 0;
    var low = !full && s.placesRestantes <= Math.ceil(s.placesTotal * 0.25);

    var card = document.createElement("div");
    card.className = "session-card" + (full ? " full" : "");
    card.setAttribute("data-reveal", "");

    var seatsLabel = full
      ? "Session complète — liste d'attente possible"
      : s.placesRestantes + " place(s) disponible(s) sur " + s.placesTotal;

    var cta = full
      ? '<a href="inscription.html?session=' + encodeURIComponent(s.id) + '" class="btn btn-outline-navy">Rejoindre la liste d\'attente</a>'
      : '<a href="inscription.html?session=' + encodeURIComponent(s.id) + '" class="btn btn-primary">S\'inscrire ' + ICON_ARROW + '</a>';

    card.innerHTML =
      '<div class="badge-row"><span class="badge">' + escapeHtml(s.domaine) + '</span><span class="badge coral">' + escapeHtml(s.mode) + '</span></div>' +
      "<h3>" + escapeHtml(s.titre) + "</h3>" +
      "<p>" + escapeHtml(s.description) + "</p>" +
      '<ul class="session-meta">' +
      "<li>" + ICON_CAL + "<span><strong>" + escapeHtml(s.dateAffichage) + "</strong>" + (s.duree ? " · " + escapeHtml(s.duree) : "") + "</span></li>" +
      (s.horaire ? "<li>" + ICON_CLOCK + "<span>" + escapeHtml(s.horaire) + "</span></li>" : "") +
      (s.lieu ? "<li>" + ICON_PIN + "<span>" + escapeHtml(s.lieu) + "</span></li>" : "") +
      "</ul>" +
      '<div class="seats-bar"><div class="seats-bar-fill' + (low ? " low" : "") + '" style="width:' + pct + '%;"></div></div>' +
      '<p style="font-size:0.82rem;color:var(--text-soft);margin:8px 0 0;">' + seatsLabel + "</p>" +
      cta;

    return card;
  }

  function render() {
    container.innerHTML = "";
    var list = SESSIONS.filter(function (s) {
      return current === "Tous" || s.domaine === current;
    });
    if (!list.length) {
      container.innerHTML = '<p style="grid-column:1/-1;text-align:center;color:var(--text-soft);">Aucune session dans ce domaine pour le moment. <a href="contact.html">Contactez-nous</a> pour être averti à l\'ouverture.</p>';
      return;
    }
    list.forEach(function (s) {
      container.appendChild(renderCard(s));
    });
  }

  if (filterBar) {
    domaines.forEach(function (d) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = d;
      if (d === current) btn.className = "active";
      btn.addEventListener("click", function () {
        current = d;
        Array.prototype.forEach.call(filterBar.querySelectorAll("button"), function (b) {
          b.classList.remove("active");
        });
        btn.classList.add("active");
        render();
      });
      filterBar.appendChild(btn);
    });
  }

  container.innerHTML = '<p style="grid-column:1/-1;text-align:center;color:var(--text-soft);">Chargement des sessions…</p>';
  chargerSessions(render);
})();
