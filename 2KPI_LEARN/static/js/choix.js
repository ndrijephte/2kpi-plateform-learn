/* Réponses proposées d'une question (formset Django) : ajout de lignes à volonté et retrait de chacune.
   Bloc attendu : [data-choix-bloc data-prefix="choix" data-libelle="Proposition"] contenant
   tbody[data-choix], template[data-choix-modele], [data-choix-ajouter], [data-choix-compte].
   Une ligne retirée est masquée et sa case DELETE cochée ; Django l'ignore ou la supprime. */
(function () {
  "use strict";
  function monter(bloc) {
    var corps = bloc.querySelector("[data-choix]"), modele = bloc.querySelector("[data-choix-modele]"),
        ajouter = bloc.querySelector("[data-choix-ajouter]"), compte = bloc.querySelector("[data-choix-compte]"),
        total = document.getElementById("id_" + (bloc.dataset.prefix || "choix") + "-TOTAL_FORMS"),
        libelle = bloc.dataset.libelle || "Proposition";
    function renumeroter() {
      var n = 0;
      corps.querySelectorAll("tr:not([hidden])").forEach(function (tr) {
        n += 1;
        tr.querySelector("[data-choix-num]").textContent = String.fromCharCode(64 + Math.min(n, 26));
        tr.querySelector("input[type=text]").setAttribute("aria-label", libelle + " " + n);
      });
      compte.textContent = n + " " + libelle.toLowerCase() + (n > 1 ? "s" : "");
    }
    ajouter.addEventListener("click", function () {
      var i = parseInt(total.value, 10);
      corps.insertAdjacentHTML("beforeend", modele.innerHTML.replace(/__prefix__/g, i));
      total.value = i + 1;
      renumeroter();
      corps.lastElementChild.querySelector("input[type=text]").focus();
    });
    corps.addEventListener("click", function (e) {
      var b = e.target.closest("[data-choix-retirer]");
      if (!b) return;
      var tr = b.closest("tr"), suivante = tr.nextElementSibling;
      while (suivante && suivante.hidden) suivante = suivante.nextElementSibling;
      tr.querySelector("input[name$='-DELETE']").checked = true;
      tr.hidden = true;
      renumeroter();
      (suivante ? suivante.querySelector("input[type=text]") : ajouter).focus();
    });
    renumeroter();
  }
  function init() { document.querySelectorAll("[data-choix-bloc]").forEach(monter); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
