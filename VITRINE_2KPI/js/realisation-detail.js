/* 2KPI — Logique de la vue détail générique (pages/realisation-detail.html)
   Lit ?projet=<id> et affiche les informations depuis js/realisations-data.js.
   Aucune modification nécessaire ici pour ajouter une réalisation : tout se
   passe dans js/realisations-data.js. */
(function () {
  "use strict";

  function param(name) {
    return new URLSearchParams(window.location.search).get(name);
  }

  var id = param("projet");
  var r = id ? getRealisationById(id) : null;

  var titreEl = document.getElementById("projet-titre");
  var catEl = document.getElementById("projet-categorie");
  var resumeEl = document.getElementById("projet-resume");
  var detailsEl = document.getElementById("projet-details");
  var chiffresEl = document.getElementById("projet-chiffres");

  if (!r) {
    if (titreEl) titreEl.textContent = "Réalisation introuvable";
    if (resumeEl) resumeEl.textContent = "Ce projet n'existe pas ou n'est plus disponible.";
    return;
  }

  document.title = r.titre + " — 2KPI";
  if (titreEl) titreEl.textContent = r.titre;
  if (catEl) catEl.textContent = r.categorie + (r.annee ? " · " + r.annee : "");
  if (resumeEl) resumeEl.textContent = r.resume;

  if (chiffresEl && r.chiffres && r.chiffres.length) {
    chiffresEl.style.display = "";
    chiffresEl.innerHTML = r.chiffres
      .map(function (c) {
        return '<div class="stat-card"><strong>' + c.valeur + "</strong><span>" + c.label + "</span></div>";
      })
      .join("");
  }

  if (detailsEl) {
    var paras = r.details && r.details.length ? r.details : [r.resume];
    detailsEl.innerHTML = paras.map(function (p) { return "<p>" + p + "</p>"; }).join("");
  }
})();
