/* 2KPI - Catalogue des formations (pages/sessions.html)
   Lit le catalogue de 2KPI Learn (js/sessions-sync.js) : chaque formation est affichée ; une session
   ouverte par l'administration apparaît avec ses dates et « S'inscrire », sinon la formation propose
   « Être prévenu(e) de l'ouverture » (liste d'intérêt, POST /api/interet/).
   Ordre : sessions ouvertes (dates fixes à venir, puis récurrentes, puis à confirmer ; complètes en
   dernier), puis les formations à venir. Filtre par domaine. */
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
  var ICON_BELL = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>';
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

  /* Date d'une session : "fixe" (début à venir), "recurrente" (ex. « Tous les samedis ») ou "a-confirmer". */
  function nature(s) {
    var debut = s.dateDebut ? new Date(s.dateDebut + "T00:00:00") : null;
    var libre = s.dateAffichage && !/^\d{1,2}\s/.test(s.dateAffichage) && s.dateAffichage !== "Date à confirmer";
    if (libre) return { type: "recurrente", debut: debut };
    if (s.dateAConfirmer || !debut || isNaN(debut) || debut < aujourdHui()) return { type: "a-confirmer", debut: null };
    return { type: "fixe", debut: debut };
  }
  var RANG = { fixe: 0, recurrente: 1, "a-confirmer": 2 };

  function blocDate(n, s) {
    if (n.type === "fixe") {
      return '<div class="session-date">' +
        '<span class="session-date-jour">' + n.debut.getDate() + "</span>" +
        '<span class="session-date-mois">' + escapeHtml(n.debut.toLocaleDateString("fr-FR", { month: "short" }).replace(".", "")) + "</span>" +
        '<span class="session-date-an">' + n.debut.getFullYear() + "</span></div>";
    }
    if (n.type === "recurrente") {
      return '<div class="session-date session-date--texte">' + ICON_REPEAT + "<span>" + escapeHtml(s.dateAffichage) + "</span></div>";
    }
    return '<div class="session-date session-date--texte session-date--attente">' + ICON_CAL + "<span>Date à confirmer</span></div>";
  }

  function faits(duree, horaire, lieu) {
    var f = [];
    if (duree) f.push("<li>" + ICON_HOURGLASS + "<span>" + escapeHtml(duree) + "</span></li>");
    if (horaire) f.push("<li>" + ICON_CLOCK + "<span>" + escapeHtml(horaire) + "</span></li>");
    if (lieu) f.push("<li>" + ICON_PIN + "<span>" + escapeHtml(lieu) + "</span></li>");
    return f.length ? '<ul class="session-facts">' + f.join("") + "</ul>" : "";
  }

  function corps(f, s) {
    var resume = (s && s.description) || f.resume;
    return '<div class="session-body">' +
      '<div class="badge-row"><span class="badge">' + escapeHtml(f.domaine) + '</span><span class="badge coral">' +
      escapeHtml((s && s.mode) || f.mode) + "</span></div>" +
      "<h3>" + escapeHtml(f.titre) + "</h3>" +
      (resume ? '<p class="session-desc">' + escapeHtml(resume) + "</p>" : "") +
      (s ? faits(s.duree || f.duree, s.horaire, s.lieu) : faits(f.duree)) +
      "</div>";
  }

  /* Une session ouverte : dates, places, « S'inscrire » */
  function ligneSession(f, s, n) {
    var full = s.placesRestantes <= 0;
    var total = s.placesTotal || 0;
    var pct = total ? Math.max(0, Math.min(100, Math.round(((total - s.placesRestantes) / total) * 100))) : 0;
    var low = !full && s.placesRestantes <= Math.ceil(total * 0.25);
    var lien = "inscription.html?session=" + encodeURIComponent(s.id);
    var places = full
      ? '<p class="session-places session-places--complet">Complet</p>'
      : '<p class="session-places' + (low ? " session-places--peu" : "") + '"><strong>' + s.placesRestantes +
        "</strong> place" + (s.placesRestantes > 1 ? "s restantes" : " restante") + " sur " + total + "</p>";
    var prix = s.prix || f.prix;
    var row = document.createElement("article");
    row.className = "session-row" + (full ? " is-full" : "");
    row.innerHTML = blocDate(n, s) + corps(f, s) +
      '<div class="session-aside">' +
        '<p class="session-etat session-etat--ouverte">Inscriptions ouvertes</p>' +
        (prix ? '<p class="session-price">' + escapeHtml(prix) + "</p>" : "") +
        places +
        '<div class="seats-bar" role="presentation"><div class="seats-bar-fill' + (low || full ? " low" : "") + '" style="width:' + pct + '%"></div></div>' +
        (full ? '<a href="' + lien + '" class="btn btn-outline-navy">Liste d\'attente</a>'
              : '<a href="' + lien + '" class="btn btn-primary">S\'inscrire ' + ICON_ARROW + "</a>") +
      "</div>";
    return row;
  }

  /* Une formation sans session ouverte : « Être prévenu(e) » et son formulaire */
  function ligneAVenir(f) {
    var row = document.createElement("article");
    row.className = "session-row is-avenir";
    var etat = f.etat === "en_cours" ? "Session en cours · prochaine à venir" : "Prochaine session bientôt annoncée";
    var id = "interet-" + f.id;
    row.innerHTML =
      '<div class="session-date session-date--texte session-date--attente">' + ICON_CAL + "<span>Dates à venir</span></div>" +
      corps(f, null) +
      '<div class="session-aside">' +
        '<p class="session-etat">' + etat + "</p>" +
        (f.prix ? '<p class="session-price">' + escapeHtml(f.prix) + "</p>" : "") +
        '<button type="button" class="btn btn-outline-navy" aria-expanded="false" aria-controls="' + id + '">' + ICON_BELL + " Être prévenu(e)</button>" +
      "</div>" +
      '<form class="interet-form" id="' + id + '" hidden novalidate>' +
        '<p class="interet-intro">Laissez vos coordonnées : nous vous écrivons dès l\'ouverture des inscriptions, avec les dates et le lien pour vous inscrire.</p>' +
        '<div class="hp" aria-hidden="true"><label>Site web<input type="text" name="site_web" tabindex="-1" autocomplete="off"></label></div>' +
        '<div class="form-row">' +
          '<div class="field"><label for="' + id + '-nom">Nom complet</label><input id="' + id + '-nom" name="nom" required autocomplete="name"></div>' +
          '<div class="field"><label for="' + id + '-email">E-mail</label><input id="' + id + '-email" name="email" type="email" required autocomplete="email"></div>' +
        "</div>" +
        '<div class="form-row">' +
          '<div class="field"><label for="' + id + '-tel">Téléphone (WhatsApp de préférence)</label><input id="' + id + '-tel" name="telephone" type="tel" required autocomplete="tel"></div>' +
          '<div class="field"><label for="' + id + '-structure">Université / structure</label><input id="' + id + '-structure" name="structure" autocomplete="organization"></div>' +
        "</div>" +
        '<fieldset class="interet-profil"><legend>Vous êtes</legend>' +
          '<label><input type="radio" name="categorie" value="etudiant" required> Étudiant(e)</label>' +
          '<label><input type="radio" name="categorie" value="professionnel"> Professionnel(le)</label>' +
        "</fieldset>" +
        '<p class="interet-erreur" role="alert" hidden></p>' +
        '<button type="submit" class="btn btn-primary">Me prévenir ' + ICON_ARROW + "</button>" +
      "</form>";
    var bouton = row.querySelector("button[aria-controls]");
    var form = row.querySelector("form");
    bouton.addEventListener("click", function () {
      form.hidden = !form.hidden;
      bouton.setAttribute("aria-expanded", form.hidden ? "false" : "true");
      if (!form.hidden) form.querySelector("input[name=nom]").focus();
    });
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      envoyerInteret(f, form);
    });
    return row;
  }

  function envoyerInteret(f, form) {
    var erreur = form.querySelector(".interet-erreur");
    var envoi = form.querySelector("button[type=submit]");
    erreur.hidden = true;
    if (!form.checkValidity()) {
      erreur.textContent = "Merci de renseigner votre nom, un e-mail valide, votre téléphone et votre profil.";
      erreur.hidden = false;
      form.reportValidity();
      return;
    }
    var donnees = { formation: f.id };
    new FormData(form).forEach(function (v, k) { donnees[k] = v; });
    envoi.disabled = true;
    fetch(LEARN_URL + "/api/interet/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(donnees) })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (!res.ok) throw new Error(res.j.erreur || "Vérifiez les informations saisies.");
        form.innerHTML = '<p class="interet-merci" role="status">C\'est noté&nbsp;! Nous vous écrirons à <strong>' +
          escapeHtml(donnees.email) + "</strong> dès l'ouverture des inscriptions à « " + escapeHtml(f.titre) + " ».</p>";
      })
      .catch(function (err) {
        erreur.textContent = (err && err.message && err.message !== "Failed to fetch") ? err.message
          : "Envoi impossible pour le moment. Écrivez-nous à contacts@2kpinnov.org.";
        erreur.hidden = false;
        envoi.disabled = false;
      });
  }

  function lignes() {
    var ouvertes = [], aVenir = [];
    CATALOGUE.forEach(function (f) {
      if (current !== TOUS && f.domaine !== current) return;
      if (f.sessions && f.sessions.length) {
        f.sessions.forEach(function (s) { ouvertes.push({ f: f, s: s, n: nature(s) }); });
      } else {
        aVenir.push(f);
      }
    });
    ouvertes.sort(function (a, b) {
      var cA = a.s.placesRestantes <= 0, cB = b.s.placesRestantes <= 0;
      if (cA !== cB) return cA ? 1 : -1;
      if (RANG[a.n.type] !== RANG[b.n.type]) return RANG[a.n.type] - RANG[b.n.type];
      if (a.n.type === "fixe") return a.n.debut - b.n.debut;
      return String(a.f.titre).localeCompare(String(b.f.titre), "fr");
    });
    aVenir.sort(function (a, b) { return String(a.titre).localeCompare(String(b.titre), "fr"); });
    return { ouvertes: ouvertes, aVenir: aVenir };
  }

  function render() {
    container.innerHTML = "";
    var l = lignes();
    if (countEl) {
      var ids = {};
      l.ouvertes.forEach(function (x) { ids[x.f.id] = true; });
      var nf = l.aVenir.length + Object.keys(ids).length;
      countEl.textContent = nf + " formation" + (nf > 1 ? "s" : "") + " · " +
        (l.ouvertes.length ? l.ouvertes.length + " session" + (l.ouvertes.length > 1 ? "s" : "") + " ouverte" +
          (l.ouvertes.length > 1 ? "s" : "") + " aux inscriptions" : "aucune session ouverte pour le moment");
    }
    if (!l.ouvertes.length && !l.aVenir.length) {
      container.innerHTML = '<p class="sessions-empty">Aucune formation dans ce domaine pour le moment. ' +
        '<a href="contact.html">Contactez-nous</a> pour une formation sur mesure.</p>';
      return;
    }
    l.ouvertes.forEach(function (x) { container.appendChild(ligneSession(x.f, x.s, x.n)); });
    if (l.ouvertes.length && l.aVenir.length) {
      var sep = document.createElement("h2");
      sep.className = "sessions-separateur";
      sep.textContent = "Prochaines sessions à venir";
      container.appendChild(sep);
    }
    l.aVenir.forEach(function (f) { container.appendChild(ligneAVenir(f)); });
  }

  function renderFilters() {
    if (!filterBar) return;
    filterBar.innerHTML = "";
    var presents = DOMAINES.filter(function (d) { return CATALOGUE.some(function (f) { return f.domaine === d; }); });
    if (presents.length < 2) return;
    [TOUS].concat(presents).forEach(function (d) {
      var n = d === TOUS ? CATALOGUE.length : CATALOGUE.filter(function (f) { return f.domaine === d; }).length;
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

  container.innerHTML = '<p class="sessions-empty">Chargement du catalogue…</p>';
  chargerCatalogue(function (ok) {
    if (!ok || !CATALOGUE) {
      container.innerHTML = '<p class="sessions-empty">Le catalogue est momentanément indisponible. Réessayez dans un instant ou ' +
        '<a href="contact.html">contactez-nous</a> : nous vous répondrons rapidement.</p>';
      return;
    }
    renderFilters();
    render();
  });
})();
