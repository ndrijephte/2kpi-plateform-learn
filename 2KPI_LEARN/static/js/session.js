/* Page d'une session (templates/agenda/session.html) : valeurs habituelles de la formation, nom proposé,
   aperçu en direct de la carte du site vitrine et conditions de publication mises à jour pendant la saisie.
   La carte reprend VITRINE_2KPI/js/sessions-catalog.js (même contenu, mêmes règles d'affichage). */
(function () {
  "use strict";
  var form = document.getElementById("session");
  if (!form) return;
  var FORMATIONS = JSON.parse(document.getElementById("formations-data").textContent);
  var INSCRITS = JSON.parse(document.getElementById("inscrits-data").textContent) || 0;
  var carte = form.querySelector("[data-apercu]");

  var SVG = function (d, w) {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="' + (w || 1.8) +
      '" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' + d + "</svg>";
  };
  var ICO = {
    sablier: SVG('<path d="M6 2h12M6 22h12M7 2c0 5 10 5 10 10S7 17 7 22M17 2c0 5-10 5-10 10s10 5 10 10"/>'),
    horloge: SVG('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'),
    lieu: SVG('<path d="M12 22s7-7.4 7-12a7 7 0 1 0-14 0c0 4.6 7 12 7 12Z"/><circle cx="12" cy="10" r="2.5"/>'),
    repete: SVG('<path d="M17 2l4 4-4 4"/><path d="M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4"/><path d="M21 13v2a3 3 0 0 1-3 3H3"/>'),
    calendrier: SVG('<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 10h18"/>'),
    ok: SVG('<path d="M20 6 9 17l-5-5"/>', 2.5),
    ko: SVG('<path d="M18 6 6 18"/><path d="m6 6 12 12"/>', 2.5)
  };

  function esc(t) {
    return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c];
    });
  }
  function champ(n) { return form.elements[n]; }
  function val(n) {
    var c = champ(n);
    if (!c) return "";
    return c.type === "checkbox" ? c.checked : (c.value || "").trim();
  }
  function texte(n) {
    var c = champ(n);
    return c && c.options && c.selectedIndex >= 0 ? c.options[c.selectedIndex].text : val(n);
  }
  function formation() {
    var id = val("formation");
    return FORMATIONS[id] || FORMATIONS[Object.keys(FORMATIONS)[0]] || {};
  }

  // Un champ modifié à la main n'est plus pré-rempli automatiquement.
  form.addEventListener("input", function (e) { if (e.target.name) e.target.dataset.touche = "1"; });
  function proposer(n, v) {
    var c = champ(n);
    if (!c || c.dataset.touche || v == null) return;
    if (c.type === "checkbox") c.checked = !!v; else c.value = v;
  }
  function nomPropose() {
    var f = formation(), d = val("date_debut");
    if (!f.titre || !d) return "";
    var mois = new Date(d + "T00:00:00").toLocaleDateString("fr-FR", {month: "long", year: "numeric"});
    return f.titre + " - Session de " + mois;
  }
  function preRemplir() {  // assistant de création uniquement (le champ formation n'existe qu'à la création)
    if (!champ("formation")) return;
    var f = formation();
    ["domaine", "mode", "duree", "prix", "afficher_prix"].forEach(function (n) { proposer(n, f[n]); });
    proposer("nom", nomPropose());
  }

  function blocDate() {
    var libre = val("date_affichage"), d = val("date_debut");
    if (libre) return '<div class="session-date session-date--texte">' + ICO.repete + "<span>" + esc(libre) + "</span></div>";
    var debut = d ? new Date(d + "T00:00:00") : null, auj = new Date();
    auj.setHours(0, 0, 0, 0);
    if (!debut || isNaN(debut) || debut < auj) {
      return '<div class="session-date session-date--texte session-date--attente">' + ICO.calendrier + "<span>Date à confirmer</span></div>";
    }
    return '<div class="session-date"><span class="session-date-jour">' + debut.getDate() + '</span><span class="session-date-mois">' +
      esc(debut.toLocaleDateString("fr-FR", {month: "short"}).replace(".", "")) + '</span><span class="session-date-an">' +
      debut.getFullYear() + "</span></div>";
  }

  function apercu() {
    var f = formation(), mode = texte("mode") || f.mode || "";
    var lieu = val("lieu") || (mode === "En ligne" ? "En ligne (visioconférence)" : "");
    var faits = [[val("duree"), ICO.sablier], [val("horaire"), ICO.horloge], [lieu, ICO.lieu]]
      .filter(function (x) { return x[0]; })
      .map(function (x) { return "<li>" + x[1] + "<span>" + esc(x[0]) + "</span></li>"; }).join("");
    var total = parseInt(val("places_total"), 10) || 0, ailleurs = parseInt(val("places_hors_plateforme"), 10) || 0;
    var reste = Math.max(0, total - INSCRITS - ailleurs), complet = reste <= 0;
    var pct = total ? Math.max(0, Math.min(100, Math.round(((total - reste) / total) * 100))) : 0;
    var peu = !complet && reste <= Math.ceil(total * 0.25);
    var prix = val("afficher_prix") ? val("prix") : "";
    var resume = val("description_vitrine") || f.resume || "";
    carte.className = "apercu-carte" + (complet ? " is-full" : "");
    carte.innerHTML = blocDate() +
      '<div class="session-body"><div class="badge-row"><span class="badge">' + esc(texte("domaine") || f.domaine || "") +
      '</span><span class="badge coral">' + esc(mode) + "</span></div><h3>" + esc(f.titre || "") + "</h3>" +
      (resume ? '<p class="session-desc">' + esc(resume) + "</p>" : "") +
      (faits ? '<ul class="session-facts">' + faits + "</ul>" : "") + "</div>" +
      '<div class="session-aside"><p class="session-etat session-etat--ouverte">Inscriptions ouvertes</p>' +
      (prix ? '<p class="session-price">' + esc(prix) + "</p>" : "") +
      (complet ? '<p class="session-places session-places--complet">Complet</p>'
               : '<p class="session-places' + (peu ? " session-places--peu" : "") + '"><strong>' + reste + "</strong> place" +
                 (reste > 1 ? "s restantes" : " restante") + " sur " + total + "</p>") +
      '<div class="seats-bar"><div class="seats-bar-fill' + (peu || complet ? " low" : "") + '" style="width:' + pct + '%"></div></div>' +
      '<span class="apercu-btn">' + (complet ? "Liste d'attente" : "S'inscrire") + "</span></div>";
  }

  function condition(cle, ok, detail) {
    var li = form.querySelector('[data-cond="' + cle + '"]');
    if (!li) return;
    li.className = ok ? "ok" : "ko";
    li.querySelector("[data-puce]").innerHTML = ok ? ICO.ok : ICO.ko;
    if (detail != null) li.querySelector("[data-detail]").textContent = detail;
  }
  function conditions() {
    if (champ("formation")) {
      var f = formation();
      condition("formation", !!f.pret, f.detail || "");
    }
    condition("formateur", !!val("formateur"), val("formateur") ? texte("formateur") : "À choisir à l'étape 1.");
    var places = parseInt(val("places_total"), 10) || 0;
    condition("places", places > 0, places > 0 ? places + " place(s)" : "À renseigner à l'étape 2.");
    var bouton = form.querySelector("[data-publier]"), aide = form.querySelector("[data-publier-aide]");
    if (bouton) {
      var manque = !!form.querySelector("[data-conditions] li.ko");
      bouton.disabled = manque;
      if (aide) aide.hidden = !manque;
    }
  }

  function maj() { apercu(); conditions(); }
  form.addEventListener("input", maj);
  form.addEventListener("change", function (e) {
    if (e.target.name === "formation" || e.target.name === "date_debut") preRemplir();
    maj();
  });
  if (champ("formation") && !champ("nom").value) preRemplir();
  maj();
})();
