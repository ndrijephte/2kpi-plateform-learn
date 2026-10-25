/* Éditeur de texte mis en forme (consignes d'exercice, notifications).
   Remplace chaque <textarea data-editeur> par une barre d'outils et une zone éditable ; le textarea
   (masqué) reçoit le HTML à chaque frappe. Le serveur refiltre tout (apps/core/texte_riche.py). */
(function () {
  "use strict";
  var TAGS = ["P", "DIV", "BR", "B", "STRONG", "I", "EM", "U", "S", "UL", "OL", "LI", "A"];
  var SVG = function (d) {
    return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' + d + "</svg>";
  };
  var OUTILS = [
    {cmd: "bold", titre: "Gras (Ctrl+B)", ico: '<path d="M6 12h9a4 4 0 0 1 0 8H7a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h7a4 4 0 0 1 0 8"/>'},
    {cmd: "italic", titre: "Italique (Ctrl+I)", ico: '<line x1="19" x2="10" y1="4" y2="4"/><line x1="14" x2="5" y1="20" y2="20"/><line x1="15" x2="9" y1="4" y2="20"/>'},
    {cmd: "underline", titre: "Souligné (Ctrl+U)", ico: '<path d="M6 4v6a6 6 0 0 0 12 0V4"/><line x1="4" x2="20" y1="20" y2="20"/>'},
    null,
    {cmd: "insertUnorderedList", titre: "Liste à puces", ico: '<path d="M3 12h.01"/><path d="M3 18h.01"/><path d="M3 6h.01"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M8 6h13"/>'},
    {cmd: "insertOrderedList", titre: "Liste numérotée", ico: '<path d="M10 12h11"/><path d="M10 18h11"/><path d="M10 6h11"/><path d="M4 10h2"/><path d="M4 6h1v4"/><path d="M6 18H4c0-1 2-2 2-3s-1-1.5-2-1"/>'},
    null,
    {cmd: "createLink", titre: "Insérer un lien", ico: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>'},
    {cmd: "removeFormat", titre: "Effacer la mise en forme", ico: '<path d="M4 7V4h16v3"/><path d="M5 20h6"/><path d="M13 4 8 20"/><path d="m15 15 5 5"/><path d="m20 15-5 5"/>'}
  ];
  var ETATS = ["bold", "italic", "underline", "insertUnorderedList", "insertOrderedList"];

  // Ne garde que les balises autorisées, sans attribut (sauf href http(s)/mailto) : contenu initial et collages.
  function propre(html) {
    var doc = new DOMParser().parseFromString("<body>" + html + "</body>", "text/html");
    (function nettoie(n) {
      Array.prototype.slice.call(n.childNodes).forEach(function (c) {
        if (c.nodeType === 3) return;
        if (c.nodeType !== 1 || /^(SCRIPT|STYLE|META|LINK|TITLE)$/.test(c.tagName)) { c.remove(); return; }
        nettoie(c);
        if (TAGS.indexOf(c.tagName) < 0) {  // balise inconnue (span, font…) : on garde son texte
          while (c.firstChild) c.parentNode.insertBefore(c.firstChild, c);
          c.remove(); return;
        }
        var href = c.tagName === "A" ? (c.getAttribute("href") || "") : "";
        Array.prototype.slice.call(c.attributes).forEach(function (a) { c.removeAttribute(a.name); });
        if (c.tagName === "A") {
          if (/^(https?:\/\/|mailto:)/i.test(href)) c.setAttribute("href", href);
          else { while (c.firstChild) c.parentNode.insertBefore(c.firstChild, c); c.remove(); }
        }
      });
    })(doc.body);
    return doc.body.innerHTML;
  }

  function esc(t) {
    var d = document.createElement("div");
    d.textContent = t;
    return d.innerHTML;
  }

  function texteVersHtml(t) {
    return esc(t).split(/\n{2,}/).map(function (p) { return "<p>" + p.replace(/\n/g, "<br>") + "</p>"; }).join("");
  }

  function monter(ta) {
    var boite = document.createElement("div"), barre = document.createElement("div"), zone = document.createElement("div");
    boite.className = "editeur";
    barre.className = "editeur-barre";
    barre.setAttribute("role", "toolbar");
    barre.setAttribute("aria-label", "Mise en forme du texte");
    zone.className = "editeur-zone texte-riche";
    zone.contentEditable = "true";
    zone.setAttribute("role", "textbox");
    zone.setAttribute("aria-multiline", "true");
    if (ta.placeholder) zone.dataset.placeholder = ta.placeholder;
    var label = ta.id && document.querySelector('label[for="' + ta.id + '"]');
    if (label) {
      label.id = label.id || ta.id + "-label";
      zone.setAttribute("aria-labelledby", label.id);
      label.addEventListener("click", function (e) { e.preventDefault(); zone.focus(); });
    }
    if (ta.getAttribute("aria-describedby")) zone.setAttribute("aria-describedby", ta.getAttribute("aria-describedby"));

    var boutons = {};
    OUTILS.forEach(function (o) {
      if (!o) { var sep = document.createElement("span"); sep.className = "editeur-sep"; barre.appendChild(sep); return; }
      var b = document.createElement("button");
      b.type = "button";
      b.className = "editeur-btn";
      b.title = o.titre;
      b.setAttribute("aria-label", o.titre);
      if (ETATS.indexOf(o.cmd) >= 0) b.setAttribute("aria-pressed", "false");
      b.innerHTML = SVG(o.ico);
      b.addEventListener("mousedown", function (e) { e.preventDefault(); });  // garde la sélection
      b.addEventListener("click", function () { agir(o.cmd); });
      boutons[o.cmd] = b;
      barre.appendChild(b);
    });

    function agir(cmd) {
      zone.focus();
      if (cmd === "createLink") {
        var url = window.prompt("Adresse du lien (https://…)", "https://");
        if (!url || url === "https://") return;
        if (!/^(https?:\/\/|mailto:)/i.test(url)) url = "https://" + url;
        if (window.getSelection().isCollapsed) document.execCommand("insertHTML", false, '<a href="' +
          esc(url).replace(/"/g, "%22") + '">' + esc(url) + "</a>");
        else document.execCommand("createLink", false, url);
      } else if (cmd === "removeFormat") {
        document.execCommand("removeFormat");
        document.execCommand("unlink");
      } else {
        document.execCommand(cmd);
      }
      synchro(); etats();
    }

    function etats() {
      if (document.activeElement !== zone) return;
      ETATS.forEach(function (c) {
        var on = false;
        try { on = document.queryCommandState(c); } catch (e) { /* navigateur sans support */ }
        boutons[c].setAttribute("aria-pressed", on ? "true" : "false");
      });
    }

    function synchro() {
      var vide = !zone.textContent.trim() && !zone.querySelector("li");
      ta.value = vide ? "" : zone.innerHTML;
      zone.classList.toggle("vide", vide);
    }

    var v = ta.value.trim();
    zone.innerHTML = !v ? "<p><br></p>" : /<\s*\/?\s*(p|div|br|b|strong|i|em|u|s|ul|ol|li|a)\b/i.test(v) ? propre(v) : texteVersHtml(v);
    ta.hidden = true;
    ta.removeAttribute("required");  // le serveur valide ; un champ masqué requis bloquerait l'envoi
    ta.parentNode.insertBefore(boite, ta);
    boite.appendChild(barre);
    boite.appendChild(zone);
    synchro();

    zone.addEventListener("input", synchro);
    zone.addEventListener("keyup", etats);
    zone.addEventListener("mouseup", etats);
    zone.addEventListener("focus", etats);
    zone.addEventListener("paste", function (e) {
      var cd = e.clipboardData;
      if (!cd) return;
      e.preventDefault();
      var html = cd.getData("text/html");
      document.execCommand("insertHTML", false, html ? propre(html) : texteVersHtml(cd.getData("text/plain")));
      synchro();
    });
    if (ta.form) ta.form.addEventListener("submit", synchro);
  }

  function init() {
    try { document.execCommand("defaultParagraphSeparator", false, "p"); document.execCommand("styleWithCSS", false, false); }
    catch (e) { /* facultatif */ }
    document.querySelectorAll("textarea[data-editeur]").forEach(monter);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
