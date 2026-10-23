/* 2KPI - Réalisations (pages/realisations.html)
   Lit le tableau REALISATIONS (js/realisations-data.js) et affiche une carte par projet, avec filtre
   par catégorie. Le détail (paragraphes, chiffres clés) se déplie sur place ; seul un projet doté
   d'une démo dédiée (vueUrl, ex. la carte interactive) ouvre une autre page.
   Lien direct vers un projet : realisations.html#<id> (le détail s'ouvre et la page y défile).
   Pour ajouter une réalisation, éditer uniquement js/realisations-data.js. */
(function () {
  "use strict";

  var container = document.getElementById("realisations-list");
  if (!container) return;

  var filterBar = document.getElementById("realisation-filters");
  var TOUS = "Tous";
  var categories = [TOUS];
  REALISATIONS.forEach(function (r) {
    if (categories.indexOf(r.categorie) === -1) categories.push(r.categorie);
  });
  var current = TOUS;

  var ICON_ARROW = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>';
  var ICON_CHEVRON = '<svg class="projet-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>';

  function escapeHtml(str) {
    return String(str == null ? "" : str).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function ouvrir(carte, ouvert) {
    var bouton = carte.querySelector(".projet-toggle");
    var panneau = carte.querySelector(".projet-detail");
    if (!bouton || !panneau) return;
    carte.classList.toggle("is-open", ouvert);
    bouton.setAttribute("aria-expanded", ouvert ? "true" : "false");
    bouton.querySelector(".projet-toggle-texte").textContent = ouvert ? "Masquer le détail" : "Voir le détail";
    if (ouvert) panneau.removeAttribute("inert"); else panneau.setAttribute("inert", "");
  }

  function renderCard(r, rang) {
    var carte = document.createElement("article");
    carte.className = "projet card-in";
    carte.id = r.id;

    var paras = (r.details && r.details.length ? r.details : []).map(function (p) {
      return "<p>" + escapeHtml(p) + "</p>";
    }).join("");
    var chiffres = (r.chiffres || []).map(function (c) {
      return '<div class="projet-chiffre"><strong>' + escapeHtml(c.valeur) + "</strong><span>" + escapeHtml(c.label) + "</span></div>";
    }).join("");
    var action;
    if (r.vueUrl) {
      action = '<a href="' + escapeHtml(r.vueUrl) + '" class="btn btn-primary projet-action">' +
        escapeHtml(r.vueLabel || "Ouvrir") + " " + ICON_ARROW + "</a>";
    } else if (paras || chiffres) {
      action = '<button type="button" class="projet-toggle" aria-expanded="false" aria-controls="detail-' + escapeHtml(r.id) + '">' +
        '<span class="projet-toggle-texte">Voir le détail</span>' + ICON_CHEVRON + "</button>";
    } else {
      action = "";
    }

    carte.innerHTML =
      '<div class="projet-repere" aria-hidden="true"><span class="projet-numero">' + (rang < 10 ? "0" : "") + rang + "</span></div>" +
      '<div class="projet-corps">' +
        '<p class="projet-meta"><span class="badge">' + escapeHtml(r.categorie) + "</span>" +
          (r.annee ? '<span class="projet-annee">' + escapeHtml(r.annee) + "</span>" : "") + "</p>" +
        "<h3>" + escapeHtml(r.titre) + "</h3>" +
        '<p class="projet-resume">' + escapeHtml(r.resume) + "</p>" +
        (r.vueUrl ? "" :
          '<div class="projet-detail" id="detail-' + escapeHtml(r.id) + '" inert><div class="projet-detail-interieur">' +
            (chiffres ? '<div class="projet-chiffres">' + chiffres + "</div>" : "") +
            paras +
          "</div></div>") +
        action +
      "</div>";

    var bouton = carte.querySelector(".projet-toggle");
    if (bouton) {
      bouton.addEventListener("click", function () {
        var ouvert = !carte.classList.contains("is-open");
        ouvrir(carte, ouvert);
        if (window.history && window.history.replaceState) {
          window.history.replaceState(null, "", ouvert ? "#" + r.id : window.location.pathname + window.location.search);
        }
      });
    }
    return carte;
  }

  function render() {
    container.innerHTML = "";
    var list = REALISATIONS.filter(function (r) { return current === TOUS || r.categorie === current; });
    if (!list.length) {
      container.innerHTML = '<p class="sessions-empty">Aucune réalisation dans cette catégorie pour le moment.</p>';
      return;
    }
    list.forEach(function (r, i) { container.appendChild(renderCard(r, i + 1)); });
  }

  if (filterBar) {
    categories.forEach(function (c) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = c;
      btn.setAttribute("aria-pressed", c === current ? "true" : "false");
      if (c === current) btn.className = "active";
      btn.addEventListener("click", function () {
        current = c;
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

  render();

  /* Lien direct : #<id> ouvre le détail du projet et y fait défiler la page */
  var cible = decodeURIComponent((window.location.hash || "").slice(1));
  var carte = cible && document.getElementById(cible);
  if (carte && carte.classList.contains("projet")) {
    ouvrir(carte, true);
    setTimeout(function () { carte.scrollIntoView({ behavior: "smooth", block: "start" }); }, 80);
  }
})();
