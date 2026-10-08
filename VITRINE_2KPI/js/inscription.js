/* 2KPI — Logique de la page d'inscription (pages/inscription.html)
   Pré-remplit la session choisie, affiche son résumé, et envoie
   l'inscription soit vers le Google Sheet (si configuré dans
   js/inscription-config.js), soit par e-mail (repli automatique). */
(function () {
  "use strict";

  var select = document.getElementById("session");
  var sessionHidden = document.getElementById("session-hidden");
  var summary = document.getElementById("session-summary");
  var form = document.getElementById("inscription-form");
  var statusOk = document.getElementById("status-success");
  var statusErr = document.getElementById("status-error");
  if (!select || !form) return;

  function paramSession() {
    var params = new URLSearchParams(window.location.search);
    return params.get("session");
  }

  function fillSelect() {
    SESSIONS.forEach(function (s) {
      var opt = document.createElement("option");
      opt.value = s.id;
      opt.textContent = s.titre + " — " + s.dateAffichage + (s.placesRestantes <= 0 ? " (complet)" : "");
      select.appendChild(opt);
    });
    var wanted = paramSession();
    if (wanted && getSessionById(wanted)) select.value = wanted;
  }

  function esc(str) {
    return String(str == null ? "" : str).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function renderSummary() {
    if (sessionHidden) sessionHidden.value = select.value;
    var s = getSessionById(select.value);
    if (!s || !summary) return;
    var full = s.placesRestantes <= 0;
    summary.innerHTML =
      "<h3>" + esc(s.titre) + "</h3>" +
      '<p style="margin:0 0 4px;"><strong>Mode :</strong> ' + esc(s.mode) + " · <strong>Dates :</strong> " + esc(s.dateAffichage) + (s.duree ? " (" + esc(s.duree) + ")" : "") + "</p>" +
      (s.horaire ? '<p style="margin:0 0 4px;"><strong>Horaire :</strong> ' + esc(s.horaire) + "</p>" : "") +
      (s.lieu ? '<p style="margin:0 0 4px;"><strong>Lieu :</strong> ' + esc(s.lieu) + "</p>" : "") +
      '<p style="margin:0; color:' + (full ? "var(--coral-dark)" : "var(--green-dark)") + '; font-weight:600;">' +
      (full ? "Session complète — votre demande sera placée en liste d'attente." : s.placesRestantes + " place(s) disponible(s) sur " + s.placesTotal) +
      "</p>";
  }

  select.disabled = true;
  chargerSessions(function () {
    select.disabled = false;
    fillSelect();
    renderSummary();
  });
  select.addEventListener("change", renderSummary);

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (statusOk) statusOk.classList.remove("visible");
    if (statusErr) statusErr.classList.remove("visible");

    var data = new FormData(form);
    var session = getSessionById(data.get("session"));
    var payload = {
      session: session ? session.titre + " (" + session.dateAffichage + ")" : data.get("session"),
      session_code: data.get("session") || "",
      site_web: data.get("site_web") || "",
      nom: data.get("nom") || "",
      email: data.get("email") || "",
      telephone: data.get("telephone") || "",
      participants: data.get("participants") || "1",
      message: data.get("message") || ""
    };

    function sendMailtoFallback() {
      var body =
        "Session : " + payload.session + "\n" +
        "Nom : " + payload.nom + "\n" +
        "Email : " + payload.email + "\n" +
        "Téléphone : " + payload.telephone + "\n" +
        "Nombre de participants : " + payload.participants + "\n\n" +
        payload.message;
      var mailto =
        "mailto:contacts@2kpinnov.org" +
        "?subject=" + encodeURIComponent("Inscription — " + payload.session) +
        "&body=" + encodeURIComponent(body);
      window.location.href = mailto;
      if (statusOk) statusOk.classList.add("visible");
    }

    function succes() {
      if (statusOk) statusOk.classList.add("visible");
      form.reset();
      renderSummary();
    }

    if (typeof isLearnConfigured === "function" && isLearnConfigured()) {
      var bouton = form.querySelector("button[type=submit]");
      if (bouton) bouton.disabled = true;
      fetch(LEARN_API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nom: payload.nom, email: payload.email, telephone: payload.telephone,
          participants: payload.participants, message: payload.message,
          session: payload.session_code, session_libelle: payload.session, site_web: payload.site_web
        })
      })
        .then(function (r) {
          return r.json().catch(function () { return {}; }).then(function (corps) { return { r: r, corps: corps }; });
        })
        .then(function (res) {
          if (res.r.ok) { succes(); return; }
          if (res.r.status === 400 || res.r.status === 429) {
            // Erreur de saisie ou trop d'envois : on l'explique, sans basculer sur l'e-mail
            var detail = res.corps.erreur || "Vérifiez les champs du formulaire (adresse e-mail, téléphone…).";
            if (statusErr) { statusErr.textContent = detail; statusErr.classList.add("visible"); }
            return;
          }
          throw new Error("HTTP " + res.r.status);
        })
        .catch(function () {
          if (statusErr) statusErr.classList.add("visible");
          sendMailtoFallback();
        })
        .then(function () { if (bouton) bouton.disabled = false; });
    } else if (typeof isAppsScriptConfigured === "function" && isAppsScriptConfigured()) {
      fetch(APPS_SCRIPT_URL, {
        method: "POST",
        mode: "no-cors",
        headers: { "Content-Type": "text/plain;charset=utf-8" },
        body: JSON.stringify(payload)
      })
        .then(function () {
          if (statusOk) statusOk.classList.add("visible");
          form.reset();
          renderSummary();
        })
        .catch(function () {
          if (statusErr) statusErr.classList.add("visible");
          sendMailtoFallback();
        });
    } else {
      sendMailtoFallback();
    }
  });
})();
