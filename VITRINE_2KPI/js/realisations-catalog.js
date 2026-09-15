/* 2KPI — Rendu du catalogue de réalisations (pages/realisations.html)
   Lit le tableau REALISATIONS (js/realisations-data.js) et affiche les
   cartes, avec filtre par catégorie. Pour ajouter une réalisation, éditer
   uniquement js/realisations-data.js. */
(function () {
  "use strict";

  var container = document.getElementById("realisations-list");
  if (!container) return;

  var filterBar = document.getElementById("realisation-filters");
  var categories = ["Tous"];
  REALISATIONS.forEach(function (r) {
    if (categories.indexOf(r.categorie) === -1) categories.push(r.categorie);
  });
  var current = "Tous";

  var ICON_ARROW = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M13 6l6 6-6 6"/></svg>';

  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function renderCard(r) {
    var card = document.createElement("div");
    card.className = "card project-card";
    card.setAttribute("data-reveal", "");

    var href = r.vueUrl ? r.vueUrl : "realisation-detail.html?projet=" + encodeURIComponent(r.id);
    var label = r.vueUrl ? (r.vueLabel || "Ouvrir") : "Voir le détail";

    card.innerHTML =
      '<span class="badge">' + escapeHtml(r.categorie) + (r.annee ? " · " + escapeHtml(r.annee) : "") + "</span>" +
      "<h3>" + escapeHtml(r.titre) + "</h3>" +
      "<p>" + escapeHtml(r.resume) + "</p>" +
      '<a href="' + href + '" class="btn btn-outline-navy" style="margin-top:auto;align-self:flex-start;">' + escapeHtml(label) + " " + ICON_ARROW + "</a>";

    return card;
  }

  function render() {
    container.innerHTML = "";
    var list = REALISATIONS.filter(function (r) {
      return current === "Tous" || r.categorie === current;
    });
    if (!list.length) {
      container.innerHTML = '<p style="grid-column:1/-1;text-align:center;color:var(--text-soft);">Aucune réalisation dans cette catégorie pour le moment.</p>';
      return;
    }
    list.forEach(function (r) {
      container.appendChild(renderCard(r));
    });
  }

  if (filterBar) {
    categories.forEach(function (c) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = c;
      if (c === current) btn.className = "active";
      btn.addEventListener("click", function () {
        current = c;
        Array.prototype.forEach.call(filterBar.querySelectorAll("button"), function (b) {
          b.classList.remove("active");
        });
        btn.classList.add("active");
        render();
      });
      filterBar.appendChild(btn);
    });
  }

  render();
})();
