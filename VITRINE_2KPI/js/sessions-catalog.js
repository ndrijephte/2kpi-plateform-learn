/* 2KPI — Rendu du catalogue de sessions (pages/sessions.html)
   Charge les sessions publiées dans 2KPI Learn (js/sessions-sync.js, repli
   sur js/sessions-data.js) et les affiche en liste ordonnée : dates fixes à venir,
   puis sessions récurrentes, puis dates à confirmer ; les sessions complètes en dernier.
   Filtre par domaine (seuls les domaines qui ont des sessions sont proposés). */
(function () {
  "use strict";

  var container = document.getElementById("sessions-list");
  if (!container) return;

  var filterBar = document.getElementById("session-filters");
  var countEl = document.getElementById("sessions-count");
  var DOMAINES = ["Socle", "Urbanisme", "Démographie", "Paysager", "Numérique"];
  var TOUS = "Toutes";
  var current = TOUS;

  var ICON_CLOCK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>';
  var ICON_PIN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M12 22s7-7.4 7-12a7 7 0 1 0-14 0c0 4.6 7 12 7 12Z"/><circle cx="12" cy="10" r="2.5"/></svg>';
  var ICON_HOURGLASS = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M6 2h12M6 22h12M7 2c0 5 10 5 10 10S7 17 7 22M17 2c0 5-10 5-10 10s10 5 10 10"/></svg>';
  var ICON_REPEAT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M17 2l4 4-4 4"/><path d="M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4"/><path d="M21 13v2a3 3 0 0 1-3 3H3"/></svg>';
  var ICON_CAL = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 10h18"/></svg>';
  var ICON_ARROW = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>';

  function escapeHtml(str) {
    return String(str == null ? "" : str).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function aujourdHui() {
    var d = new Date();
    return new Date(d.getFullYear(), d.getMonth(), d.getDate());
  }

  /* Nature de la date : "fixe" (date de début à venir), "recurrente" (ex. « Tous les samedis »)
     ou "a-confirmer" (date de début passée, ou rien d'exploitable). */
  function nature(s) {
    var debut = s.dateDebut ? new Date(s.dateDebut + "T00:00:00") : null;
    var libre = s.dateAffichage && !/^\d{1,2}\s/.test(s.dateAffichage) && s.dateAffichage !== "Date à confirmer";
    if (libre) return { type: "recurrente", debut: debut };
    if (s.dateAConfirmer || !debut || isNaN(debut) || debut < aujourdHui()) return { type: "a-confirmer", debut: null };
    return { type: "fixe", debut: debut };
  }

  var RANG = { fixe: 0, recurrente: 1, "a-confirmer": 2 };

  function trier(list) {
    return list.map(function (s) { return { s: s, n: nature(s) }; }).sort(function (a, b) {
      var complA = a.s.placesRestantes <= 0, complB = b.s.placesRestantes <= 0;
      if (complA !== complB) return complA ? 1 : -1;
      if (RANG[a.n.type] !== RANG[b.n.type]) return RANG[a.n.type] - RANG[b.n.type];
      if (a.n.type === "fixe") return a.n.debut - b.n.debut;
      return String(a.s.titre).localeCompare(String(b.s.titre), "fr");
    });
  }

  function blocDate(n, s) {
    if (n.type === "fixe") {
      return '<div class="session-date">' +
        '<span class="session-date-jour">' + n.debut.getDate() + "</span>" +
        '<span class="session-date-mois">' + escapeHtml(n.debut.toLocaleDateString("fr-FR", { month: "short" }).replace(".", "")) + "</span>" +
        '<span class="session-date-an">' + n.debut.getFullYear() + "</span></div>";
    }
    if (n.type === "recurrente") {
      return '<div class="session-date session-date--texte">' + ICON_REPEAT +
        "<span>" + escapeHtml(s.dateAffichage) + "</span></div>";
    }
    return '<div class="session-date session-date--texte session-date--attente">' + ICON_CAL +
      "<span>Date à confirmer</span></div>";
  }

  function renderRow(item) {
    var s = item.s, n = item.n;
    var full = s.placesRestantes <= 0;
    var total = s.placesTotal || 0;
    var pct = total ? Math.max(0, Math.min(100, Math.round(((total - s.placesRestantes) / total) * 100))) : 0;
    var low = !full && s.placesRestantes <= Math.ceil(total * 0.25);
    var lien = "inscription.html?session=" + encodeURIComponent(s.id);

    var faits = [];
    if (s.duree) faits.push("<li>" + ICON_HOURGLASS + "<span>" + escapeHtml(s.duree) + "</span></li>");
    if (s.horaire) faits.push("<li>" + ICON_CLOCK + "<span>" + escapeHtml(s.horaire) + "</span></li>");
    if (s.lieu) faits.push("<li>" + ICON_PIN + "<span>" + escapeHtml(s.lieu) + "</span></li>");

    var places = full
      ? '<p class="session-places session-places--complet">Complet</p>'
      : '<p class="session-places' + (low ? " session-places--peu" : "") + '"><strong>' + s.placesRestantes +
        "</strong> place" + (s.placesRestantes > 1 ? "s restantes" : " restante") + " sur " + total + "</p>";

    var row = document.createElement("article");
    row.className = "session-row" + (full ? " is-full" : "");
    row.innerHTML =
      blocDate(n, s) +
      '<div class="session-body">' +
        '<div class="badge-row"><span class="badge">' + escapeHtml(s.domaine) + '</span><span class="badge coral">' + escapeHtml(s.mode) + "</span></div>" +
        "<h3>" + escapeHtml(s.titre) + "</h3>" +
        (s.description ? '<p class="session-desc">' + escapeHtml(s.description) + "</p>" : "") +
        (faits.length ? '<ul class="session-facts">' + faits.join("") + "</ul>" : "") +
      "</div>" +
      '<div class="session-aside">' +
        (s.prix ? '<p class="session-price">' + escapeHtml(s.prix) + "</p>" : "") +
        places +
        '<div class="seats-bar" role="presentation"><div class="seats-bar-fill' + (low || full ? " low" : "") + '" style="width:' + pct + '%"></div></div>' +
        (full
          ? '<a href="' + lien + '" class="btn btn-outline-navy">Liste d\'attente</a>'
          : '<a href="' + lien + '" class="btn btn-primary">S\'inscrire ' + ICON_ARROW + "</a>") +
      "</div>";
    return row;
  }

  function render() {
    container.innerHTML = "";
    var list = trier(SESSIONS.filter(function (s) { return current === TOUS || s.domaine === current; }));
    if (countEl) {
      countEl.textContent = list.length
        ? list.length + " session" + (list.length > 1 ? "s" : "") + " ouverte" + (list.length > 1 ? "s" : "") + " aux inscriptions"
        : "";
    }
    if (!list.length) {
      container.innerHTML = '<p class="sessions-empty">Aucune session ouverte dans ce domaine pour le moment. ' +
        '<a href="contact.html">Contactez-nous</a> pour être averti à l\'ouverture.</p>';
      return;
    }
    list.forEach(function (item) { container.appendChild(renderRow(item)); });
  }

  function renderFilters() {
    if (!filterBar) return;
    filterBar.innerHTML = "";
    var presents = DOMAINES.filter(function (d) { return SESSIONS.some(function (s) { return s.domaine === d; }); });
    if (presents.length < 2) return; // un seul domaine : le filtre n'apporte rien
    [TOUS].concat(presents).forEach(function (d) {
      var n = d === TOUS ? SESSIONS.length : SESSIONS.filter(function (s) { return s.domaine === d; }).length;
      var btn = document.createElement("button");
      btn.type = "button";
      btn.innerHTML = escapeHtml(d) + ' <span class="filter-count">' + n + "</span>";
      btn.setAttribute("aria-pressed", d === current ? "true" : "false");
      if (d === current) btn.className = "active";
      btn.addEventListener("click", function () {
        current = d;
        Array.prototype.forEach.call(filterBar.querySelectorAll("button"), function (b) {
          b.classList.remove("active");
          b.setAttribute("aria-pressed", "false");
        });
        btn.classList.add("active");
        btn.setAttribute("aria-pressed", "true");
        render();
      });
      filterBar.appendChild(btn);
    });
  }

  container.innerHTML = '<p class="sessions-empty">Chargement des sessions…</p>';
  chargerSessions(function () {
    renderFilters();
    render();
  });
})();
