/* 2KPI — script unique, sans dépendance externe */
(function () {
  "use strict";

  /* Menu mobile */
  var toggle = document.querySelector(".nav-toggle");
  var links = document.querySelector(".nav-links");
  if (toggle && links) {
    toggle.addEventListener("click", function () {
      links.classList.toggle("open");
      var expanded = links.classList.contains("open");
      toggle.setAttribute("aria-expanded", expanded);
    });
    links.querySelectorAll("a").forEach(function (a) {
      a.addEventListener("click", function () { links.classList.remove("open"); });
    });
  }

  /* En local, le bouton « Espace apprenant » mène à l'app lancée sur le poste
     (python manage.py runserver) plutôt qu'à learn.2kpinnov.org */
  if (/^(localhost|127\.0\.0\.1)$/.test(window.location.hostname)) {
    document.querySelectorAll('a[href^="https://learn.2kpinnov.org"]').forEach(function (a) {
      a.href = a.getAttribute("href").replace("https://learn.2kpinnov.org", "http://127.0.0.1:8000");
    });
  }

  /* Lien de navigation actif selon la page courante */
  var current = window.location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll(".nav-links a[data-page]").forEach(function (a) {
    if (a.getAttribute("data-page") === current) {
      a.classList.add("active");
      /* Si le lien actif est dans un menu déroulant, on marque son parent */
      var parentItem = a.closest(".nav-item");
      if (parentItem) parentItem.classList.add("is-active");
    }
  });

  /* Menus déroulants : ouverture au clic (indispensable au tactile/mobile),
     le survol reste géré en CSS sur ordinateur. */
  var navItems = document.querySelectorAll(".nav-links .nav-item.has-dropdown");
  navItems.forEach(function (item) {
    var parent = item.querySelector(".nav-parent");
    if (!parent) return;
    parent.addEventListener("click", function (e) {
      e.stopPropagation();
      var isOpen = item.classList.contains("open");
      navItems.forEach(function (o) { o.classList.remove("open"); });
      if (!isOpen) {
        item.classList.add("open");
        parent.setAttribute("aria-expanded", "true");
      } else {
        parent.setAttribute("aria-expanded", "false");
      }
    });
  });
  /* Fermer les menus ouverts en cliquant ailleurs */
  document.addEventListener("click", function () {
    navItems.forEach(function (o) {
      o.classList.remove("open");
      var p = o.querySelector(".nav-parent");
      if (p) p.setAttribute("aria-expanded", "false");
    });
  });

  /* Apparition au scroll */
  var revealEls = document.querySelectorAll("[data-reveal]");
  if ("IntersectionObserver" in window && revealEls.length) {
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.15 }
    );
    revealEls.forEach(function (el) { io.observe(el); });
  } else {
    revealEls.forEach(function (el) { el.classList.add("is-visible"); });
  }

  /* Formulaire de contact : ouverture du client mail avec le message pré-rempli.
     NOTE (à l'attention de KOFFI) : ceci fonctionne sans backend mais dépend du
     client mail installé sur l'appareil du visiteur. Pour un envoi direct et
     fiable depuis le site (sans ouvrir de logiciel mail), il faudra brancher un
     service comme Formspree, EmailJS ou Netlify Forms - je peux le faire dès
     que tu choisis le service. */
  var form = document.querySelector("#contact-form");
  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var data = new FormData(form);
      var nom = data.get("nom") || "";
      var email = data.get("email") || "";
      var tel = data.get("telephone") || "";
      var objet = data.get("objet") || "Demande d'information - 2KPI";
      var message = data.get("message") || "";

      var body =
        "Nom : " + nom + "\n" +
        "Email : " + email + "\n" +
        "Téléphone : " + tel + "\n\n" +
        message;

      var mailto =
        "mailto:contacts@2kpinnov.org" +
        "?subject=" + encodeURIComponent(objet) +
        "&body=" + encodeURIComponent(body);

      window.location.href = mailto;
    });
  }

  /* Année automatique dans le footer */
  var yearEl = document.querySelector("#year");
  if (yearEl) yearEl.textContent = new Date().getFullYear();
})();
