const infoPanel = document.getElementById("info-panel");
let globalMaxSuperficie = 40000;

// Initialisation
var map = L.map("map").setView([7.5468545, -5.5470995], 9);

// ------------------------------------------------------
// %%%%%%%% Fond de carte par défaut %%%%%%%%%%
// 1/ OpenStreetMap
var osm = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
});

// 2/ Fond sombre — CartoDB Dark Matter (libre, sans clé API)
var Stadia_AlidadeSmoothDark = L.tileLayer(
  "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
  {
    maxZoom: 20,
    subdomains: "abcd",
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
  },
);

// 3/ Fond satellite — Esri World Imagery (libre, sans clé API)
var Stadia_AlidadeSatellite = L.tileLayer(
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  {
    maxZoom: 19,
    attribution:
      "Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community",
  },
);

// 4/ Fond clair — CartoDB Positron (libre, sans clé API)
var Stadia_StamenTonerLite = L.tileLayer(
  "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
  {
    maxZoom: 20,
    subdomains: "abcd",
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
  },
);

// 5/ OpenTopo
var OpenTopoMap = L.tileLayer(
  "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
  {
    maxZoom: 17,
    attribution:
      'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',
  },
);

// 6/ Stadia AlidadeSmooth
// var Stadia_AlidadeSmooth = L.tileLayer(
//   "https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.{ext}",
//   {
//     // apikey: "58784260-e150-4b46-9b00-c8824570ef84",
//     minZoom: 0,
//     maxZoom: 20,
//     attribution:
//       '&copy; <a href="https://www.stadiamaps.com/" target="_blank">Stadia Maps</a> &copy; <a href="https://openmaptiles.org/" target="_blank">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
//     ext: "png",
//   },
// );

// 6/ Fond détaillé — CartoDB Voyager (libre, sans clé API) — fond par défaut
var Stadia_AlidadeSmooth = L.tileLayer(
  "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
  {
    maxZoom: 20,
    subdomains: "abcd",
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
  },
);

let currentBaseLayer = Stadia_AlidadeSmooth;
map.addLayer(currentBaseLayer);

// %%%% Échelle graphique (bas à droite) %%%%
L.control.scale({ position: "bottomright", imperial: false, maxWidth: 160 }).addTo(map);

// %%%% Flèche du nord géographique (bas à droite) %%%%
var northArrow = L.control({ position: "bottomright" });
northArrow.onAdd = function () {
  var div = L.DomUtil.create("div", "north-arrow");
  div.innerHTML =
    '<svg viewBox="0 0 24 34" fill="none" xmlns="http://www.w3.org/2000/svg">' +
    '<polygon points="12,1 19,20 12,15 5,20" fill="#0f4061"/>' +
    '<polygon points="12,1 12,15 5,20" fill="#f97a64"/>' +
    "</svg><span>N</span>";
  return div;
};
northArrow.addTo(map);

// %%%% Fonds de carte %%%%%
var baseMaps = {
  "Carto Voyager": {
    layer: Stadia_AlidadeSmooth,
    img: "assets/img/stadia_smooth.png",
  },
  OpenStreetMap: {
    layer: osm,
    img: "assets/img/osm.png",
  },
  Satellite: {
    layer: Stadia_AlidadeSatellite,
    img: "assets/img/stadia_satellite.png",
  },
  "Carto Clair": {
    layer: Stadia_StamenTonerLite,
    img: "assets/img/stament_toner.png",
  },
  "Carto Sombre": {
    layer: Stadia_AlidadeSmoothDark,
    img: "assets/img/stadia_dark.png",
  },
  "Relief (OpenTopo)": {
    layer: OpenTopoMap,
    img: "assets/img/open_topo.png",
  },
};

// ---------------------------------------------------------------------

//%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

// Création de groupes
var groupeLimite = L.layerGroup();
var groupeDepartements = L.layerGroup();

// Définition des overlays GLOBALE
const overlays = {
  Limite: {
    layer: groupeLimite,
    type: "line",
  },
  Départements: {
    layer: groupeDepartements,
    type: "polygon",
  },
};

// Cadre pour les filtres
// function createSuperficieFilter() {
//   const filterDiv = document.createElement("div");
//   filterDiv.classList.add("filter-container");

//   filterDiv.innerHTML = `
//     <h4>Filtre Superficie</h4>
//     <label>
//       Min:
//       <input type="number" id="sup-min" value="0">
//     </label>
//     <label>
//       Max:
//       <input type="number" id="sup-max">
//     </label>
//     <button id="apply-sup-filter">Appliquer</button>
//     <button id="reset-sup-filter">Réinitialiser</button>
//   `;

//   return filterDiv;
// }

function createSuperficieFilter() {
  const filterDiv = document.createElement("div");
  filterDiv.classList.add("filter-container");

  const maxVal = globalMaxSuperficie || 40000;

  filterDiv.innerHTML = `
    <h4>Filtrer par superficie</h4>
    <div style="margin-bottom: 8px;">
      <label>Max : <b id="range-value" style="color: var(--color2);">${Math.round(maxVal)}</b> ha</label>
    </div>
    <div class="range-controls" style="display: flex; align-items: center; gap: 10px;">
      <span class="range-bound">0</span>
      <input type="range" id="sup-range" min="0" max="${maxVal}" value="${maxVal}" style="flex-grow: 1; accent-color: var(--color2);">
      <span class="range-bound" id="range-max-label">${Math.round(maxVal)}</span>
    </div>
    <div style="margin-top: 12px;">
      <button id="reset-sup-filter" style="width:100%; cursor:pointer;">Tout afficher</button>
    </div>
  `;

  // ----- LIAISON DES ÉVÉNEMENTS -----
  const slider = filterDiv.querySelector("#sup-range");
  const rangeValue = filterDiv.querySelector("#range-value");
  const resetBtn = filterDiv.querySelector("#reset-sup-filter");

  slider.addEventListener("input", () => {
    const val = parseFloat(slider.value);
    rangeValue.innerText = Math.round(val);
    applySuperficieFilter(0, val);
  });

  resetBtn.addEventListener("click", () => {
    slider.value = maxVal;
    rangeValue.innerText = Math.round(maxVal);
    applySuperficieFilter(0, maxVal);
  });

  return filterDiv;
}

// %%%%%%%%% GENERATION DYNAMIQUE DE CONTENU %%%%%%%%%%
function renderBasemaps() {
  const managerContent = document.getElementById("manager-content");
  managerContent.innerHTML = "";

  const grid = document.createElement("div");
  grid.classList.add("basemap-grid");

  Object.entries(baseMaps).forEach(([name, obj], index) => {
    const item = document.createElement("div");
    item.classList.add("basemap-item");
    const safeId = `basemap-${index}`;

    item.innerHTML = `
      <input type="radio" name="basemap" id="${safeId}" ${obj.layer === currentBaseLayer ? "checked" : ""}>
      <label for="${safeId}">
        <img src="${obj.img}" alt="${name}">
        <span>${name}</span>
      </label>
    `;

    grid.appendChild(item);

    item.querySelector("input").addEventListener("change", () => {
      if (currentBaseLayer) map.removeLayer(currentBaseLayer);
      currentBaseLayer = obj.layer;
      currentBaseLayer.addTo(map);
      currentBaseLayer.bringToBack(); // Important pour voir les données par dessus
    });
  });

  managerContent.appendChild(grid);
}

const overlaysTab = document.querySelector('[data-tab="overlays"]');
const managerContent = document.getElementById("manager-content");

function renderOverlays() {
  const managerContent = document.getElementById("manager-content");
  managerContent.innerHTML = ""; // Nettoyage

  Object.entries(overlays).forEach(([name, obj]) => {
    const label = document.createElement("label");
    label.classList.add("overlay-item"); // Utilise ta classe CSS flex

    let symbol =
      obj.type === "line"
        ? `<span class="symbol line"></span>`
        : `<span class="symbol polygon"></span>`;

    label.innerHTML = `
      <input type="checkbox" ${map.hasLayer(obj.layer) ? "checked" : ""}>
      ${symbol}
      <span style="flex-grow: 1;">${name}</span>
    `;

    managerContent.appendChild(label);

    label.querySelector("input").addEventListener("change", (e) => {
      if (e.target.checked) {
        map.addLayer(obj.layer);
      } else {
        map.removeLayer(obj.layer);
      }
    });
  });

  // Séparateur
  managerContent.appendChild(document.createElement("hr"));

  // Ajout du filtre
  managerContent.appendChild(createSuperficieFilter());
}

// --- GESTION DES ONGLETS ---
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    // 1. Gérer l'apparence visuelle des onglets
    document
      .querySelectorAll(".tab")
      .forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");

    // 2. Charger le bon contenu
    if (tab.dataset.tab === "overlays") {
      renderOverlays();
    } else {
      renderBasemaps();
    }
  });
});

// --- INITIALISATION AU CHARGEMENT ---
// On affiche les couches par défaut au démarrage
renderOverlays();

// GESTION  DES ONGLETS OUVERTURE / FERMETURE
const manager = document.getElementById("layer-manager");
const toggleBtn = document.getElementById("manager-toggle");
const toggleIcon = toggleBtn.querySelector("i");

// état initial
manager.classList.add("collapsed");

toggleBtn.addEventListener("click", () => {
  manager.classList.toggle("collapsed");

  if (manager.classList.contains("collapsed")) {
    toggleIcon.classList.remove("fa-xmark");
    toggleIcon.classList.add("fa-bars");
  } else {
    toggleIcon.classList.remove("fa-bars");
    toggleIcon.classList.add("fa-xmark");
  }
});

// %%%%%%%%% POUR GENERER DYNAMIQUEMENT LES LISTES %%%%%%
// function buildLayerPanel() {
//   const basemapList = document.getElementById("basemaps-control");
//   const overlayList = document.getElementById("layers-control");

// Nettoyer avant génération
// basemapList.innerHTML = "";
// overlayList.innerHTML = "";

// ========================
// FONDS DE CARTE (radio)
// ========================
// Object.entries(baseMaps).forEach(([name, obj], index) => {
//   const label = document.createElement("label");

//   label.innerHTML = `
//   <input type="radio" name="basemap" ${obj.layer === currentBaseLayer ? "checked" : ""}>
//   ${name}
// `;

//   basemapList.appendChild(label);

//   label.querySelector("input").addEventListener("change", () => {
//     if (currentBaseLayer) {
//       map.removeLayer(currentBaseLayer);
//     }

//     currentBaseLayer = obj.layer;
//     map.addLayer(currentBaseLayer);
//   });
// });

// ========================
// COUCHES (checkbox)
// ========================
//   Object.entries(overlays).forEach(([name, layer]) => {
//     const label = document.createElement("label");

//     label.innerHTML = `
//       <input type="checkbox" checked>
//       ${name}
//     `;

//     overlayList.appendChild(label);

//     map.addLayer(layer);

//     label.querySelector("input").addEventListener("change", (e) => {
//       if (e.target.checked) {
//         map.addLayer(layer);
//       } else {
//         map.removeLayer(layer);
//       }
//     });
//   });
// }

// %%%%%% Activer l’ouverture / fermeture au clic %%%%%%
document.querySelectorAll(".control-header").forEach((header) => {
  header.addEventListener("click", () => {
    const content = header.nextElementSibling;
    const isOpen = content.style.display === "block";

    // Reset tout
    document.querySelectorAll(".control-content").forEach((panel) => {
      panel.style.display = "none";
    });

    document.querySelectorAll(".control-header").forEach((h) => {
      h.classList.remove("active");
    });

    if (!isOpen) {
      content.style.display = "block";
      header.classList.add("active");
    }
  });
});

// %%%%% CARTE CHLOROPLETE AVEC LES DONNEES DE POPULATION %%%%%%
// 1) Définition des classes de couleurs
const classesPopulation = [
  { min: 0, max: 300000, color: "#edf8fb", label: "< 300 000" },
  { min: 300000, max: 600000, color: "#abdda4", label: "300 000 – 600 000" },
  { min: 600000, max: 900000, color: "#ffffbf", label: "600 000 – 900 000" },
  { min: 900000, max: 1200000, color: "#fdae61", label: "900 000 – 1 200 000" },
  { min: 1200000, max: Infinity, color: "#d7191c", label: "> 1 200 000" },
];

// 2) Création de la fonction couleur
function getColor(pop) {
  return classesPopulation.find((c) => pop >= c.min && pop < c.max).color;
}

// Limites de la Côte d'Ivoire (données locales embarquées : LIMITE_CI)
function wfsMapLayerLimit() {
  try {
    const data = LIMITE_CI;
    const limitLayer = L.geoJSON(data, {
      style: {
        color: "#000000",
        weight: 3,
        fill: false,
      },
    });

    groupeLimite.addLayer(limitLayer);
    map.addLayer(groupeLimite);
  } catch (err) {
    console.error("Erreur chargement limite :", err);
  }
}

// %%%%%%%% STYLE AU DEPLACEMENT SUR UN DPT DONNES %%%%%%%%%%%
// style normal
function styleDepartements(feature) {
  return {
    fill: true,
    fillColor: getColor(feature.properties.population),
    weight: 1,
    color: "#555",
    fillOpacity: 1,
  };
}

// style au survol
function highlightFeature(e) {
  const layer = e.target;

  // On vérifie si la couche est visible avant de surligner
  // if (layer.options.opacity === 0) return;

  layer.setStyle({
    fillColor: "#b4e9fd",
    fillOpacity: 1,
  });

  layer.bringToFront();
}

// retour au style initial
function resetHighlight(e) {
  departementsLayer.resetStyle(e.target);
}

let departementsLayer;
// const titre = document.querySelector("h1");

// Département de la Côte d'Ivoire
function wfsMapLayerDepartements() {
  try {
    const data = DEPARTEMENT_CI;
    const superficies = data.features.map((f) => f.properties.superficie || 0);
    globalMaxSuperficie = Math.max(...superficies);

    departementsLayer = L.geoJSON(data, {
      style: styleDepartements,
      onEachFeature: (feature, layer) => {
        layer.on({
          mouseover: (e) => {
            highlightFeature(e);
            updateInfo(feature);
          },
          mouseout: (e) => {
            resetHighlight(e);
            infoPanel.innerHTML = `<h2>Informations</h2><p>Survolez un département</p>`;
          },
        });
      },
    });

    groupeDepartements.addLayer(departementsLayer);
    map.addLayer(groupeDepartements);
    map.fitBounds(departementsLayer.getBounds());
    map.invalidateSize();

    // Maintenant que le max est connu, on (re)génère le filtre
    renderOverlays();
  } catch (err) {
    console.error("Erreur chargement départements :", err);
  }
}

// Ajout de couche de contrôle
// new L.Control.Geocoder().addTo(map);

// 3) Création la légende Leaflet
const legend = L.control({ position: "bottomleft" });

legend.onAdd = function () {
  const div = L.DomUtil.create("div", "legend");

  div.innerHTML = "<h4>Population</h4>";

  classesPopulation.forEach((c) => {
    div.innerHTML += `
      <div>
        <span style="
          background:${c.color};
          width:18px;
          height:18px;
          display:inline-block;
          margin-right:8px;
        "></span>
        ${c.label}
      </div>
    `;
  });

  return div;
};

legend.addTo(map);

// Mettre à jour les panneaux / Création du résumé des informations
function updateInfo(feature) {
  const props = feature.properties;

  infoPanel.innerHTML = `
    <h2>${props.departement}</h2>
    <p><b>Région :</b> ${props.region}</p>
    <p><b>Population :</b> ${(props.population || 0).toLocaleString()}</p>
    <p><b>Superficie :</b> ${(props.superficie * 0.01).toFixed(3) || "N/A"} km²</p>
    <p><b>Densité :</b> ${(props.population / props.superficie).toFixed(3) || "N/A"} hbts/km²</p>
  `;
}

// %%%%%%%%%% POUR FILTRER A PARTIR DES DONNES DE POPULATION %%%%%%%%%
// Appliquer le filtre
function applySuperficieFilter(min, max) {
  if (!departementsLayer) return;

  departementsLayer.eachLayer((layer) => {
    // ATTENTION : Vérifie bien que le nom dans ton GeoJSON est 'superficie'
    const sup =
      layer.feature.properties.superficie || layer.feature.properties.area || 0;

    if (sup >= min && sup <= max) {
      // On remet le style normal si c'est dans la borne
      layer.setStyle({ opacity: 1, fillOpacity: 1, stroke: true });
      layer.options.interactive = true; // Permet de cliquer/survoler encore
    } else {
      // On cache complètement si c'est hors borne
      layer.setStyle({ opacity: 0, fillOpacity: 0, stroke: false });
      layer.options.interactive = false; // Désactive les popups/survols
    }
  });
}

// %%%%%%%%%% Appel des fonctions %%%%%%%%%%%
renderBasemaps();
wfsMapLayerLimit();
wfsMapLayerDepartements();

// Corrige le rendu partiel des tuiles lorsque la carte est affichée dans un
// cadre (iframe) ou après un redimensionnement de la fenêtre.
window.addEventListener("load", () => setTimeout(() => map.invalidateSize(), 200));
window.addEventListener("resize", () => map.invalidateSize());
