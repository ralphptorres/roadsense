const COUNTRIES = {
  thailand: { center: [101.0, 13.5], zoom: 5.4, label: "Thailand" },
  maharashtra: { center: [76.0, 19.0], zoom: 6.2, label: "Maharashtra" },
};

const SSS_STOPS = [
  [0, "#2166ac"],
  [40, "#67a9cf"],
  [55, "#f7f2e8"],
  [70, "#f0a202"],
  [100, "#d1382f"],
];

let PHYSICS_STOPS = null; // computed per-country once data loads, since range varies
let TRAFFIC_STOPS = null;
let FOOTTRAFFIC_STOPS = null;

const JURISDICTION_STOPS = [
  [0, "#f7f2e8"],
  [2, "#f0d78c"],
  [5, "#f0a202"],
  [10, "#d1382f"],
  [20, "#7a1810"],
];

// maplibre text-field rendering needs a glyphs (SDF font) server configured
// on the style, which we don't have, and SDF text can't render color emoji
// regardless, so category markers are colored circles, not pictograms.
const POI_COLOR = { school: "#3f7fbf", hospital: "#d1382f", market: "#2f9e5c", other: "#8a8478" };
const POI_LABEL = { school: "School", hospital: "Hospital", market: "Market/Shop", other: "Other" };

// both basemaps are added at init and toggled via visibility, rather than
// swapping the whole map style, since map.setStyle() wipes custom
// sources/layers (our segments data) and re-adding them on every theme
// toggle is more fragile than just hiding/showing two raster layers.
function cartoTiles(variant) {
  return ["a", "b", "c"].map((s) => `https://${s}.basemaps.cartocdn.com/${variant}/{z}/{x}/{y}@2x.png`);
}

const BASE_STYLE = {
  version: 8,
  sources: {
    "carto-light-src": { type: "raster", tiles: cartoTiles("light_all"), tileSize: 256, attribution: "© OpenStreetMap contributors © CARTO" },
    "carto-dark-src": { type: "raster", tiles: cartoTiles("dark_all"), tileSize: 256, attribution: "© OpenStreetMap contributors © CARTO" },
  },
  layers: [
    { id: "carto-light", type: "raster", source: "carto-light-src", layout: { visibility: "visible" } },
    { id: "carto-dark", type: "raster", source: "carto-dark-src", layout: { visibility: "none" } },
  ],
};

let map;
let currentCountry = "thailand";
let currentLayer = "sss";
let currentAudience = "policy";
let currentTheme = localStorage.getItem("roadsense-theme") || "light";
let dataCache = {};

// mirrors the intervention-mapping table in
// p0-submission/methodology-plan.md's Layer 4 section: dominant component
// combination -> the type of fix a transport ministry would actually act
// on, not just a numeric score. weaves in the segment's own numbers
// (ssgRatio, osr) rather than a fixed boilerplate sentence, since a pure
// template made every top-ranked segment read identically.
function intensityWord(pctile) {
  if (pctile > 97) return "drastically";
  if (pctile > 90) return "substantially";
  return "moderately";
}

function policyNarrative({ ssgPctile, osrPctile, ssgRatio, osr }) {
  const highSSG = ssgPctile > 70;
  const highOSR = osrPctile > 70;
  if (highSSG && !highOSR) {
    const mult = ssgRatio != null ? `${ssgRatio.toFixed(1)}x` : "far";
    return `The posted limit is ${intensityWord(ssgPctile)} above what's survivable here (${mult} the Safe System threshold), yet drivers already travel close to a safe speed. Recommended fix: <b>lower the posted speed limit</b> to match how the road is actually driven.`;
  }
  if (highSSG && highOSR) {
    const over = osr != null ? `${osr >= 0 ? "+" : ""}${osr.toFixed(0)} km/h` : "well above";
    return `Both the posted limit and actual driving speed (${over} beyond what this road's design predicts) are ${intensityWord(Math.max(ssgPctile, osrPctile))} unsafe. Recommended fix: <b>physical road redesign</b>, a new sign alone won't change how this road is being driven.`;
  }
  if (!highSSG && highOSR) {
    const over = osr != null ? `${osr >= 0 ? "+" : ""}${osr.toFixed(0)} km/h` : "well above";
    return `The posted limit is broadly reasonable, but drivers run ${intensityWord(osrPctile)} faster than the road's design predicts (${over}). Recommended fix: <b>enforcement or traffic-calming measures</b>, not a sign change.`;
  }
  return "Elevated across several factors at once rather than one clear cause, worth a site visit before deciding on a fix.";
}

function vueBadge(vueScore) {
  return vueScore > 70 ? '<span class="tag tag-vue">HIGH PEDESTRIAN/CYCLIST EXPOSURE</span>' : "";
}

function colorExpr(stops) {
  const expr = ["interpolate", ["linear"], ["get", stops.prop]];
  for (const [v, c] of stops.stops) expr.push(v, c);
  return expr;
}

function buildLegend(stops, title) {
  const el = document.getElementById("legend");
  const gradient = stops.stops.map(([, c]) => c).join(", ");
  const lo = stops.stops[0][0];
  const hi = stops.stops[stops.stops.length - 1][0];
  el.innerHTML = `
    <div class="legend-title">${title}</div>
    <div class="legend-scale" style="background: linear-gradient(90deg, ${gradient})"></div>
    <div class="legend-labels"><span>${lo}${stops.unit || ""}</span><span>${hi}${stops.unit || ""}</span></div>
  `;
}

async function loadCountry(country) {
  if (dataCache[country]) return dataCache[country];
  const [geojson, ranked, jurisdictions, pois] = await Promise.all([
    fetch(`data/${country}.geojson`).then((r) => r.json()),
    fetch(`data/${country}_ranked.json`).then((r) => r.json()),
    fetch(`data/${country}_jurisdictions.geojson`).then((r) => r.json()),
    fetch(`data/${country}_pois.geojson`).then((r) => r.json()),
  ]);
  dataCache[country] = { geojson, ranked, jurisdictions, pois };
  return dataCache[country];
}

function computePhysicsStops(geojson) {
  const vals = geojson.features.map((f) => f.properties.ssd_excess_m).filter((v) => v != null).sort((a, b) => a - b);
  const q = (p) => vals[Math.floor(p * (vals.length - 1))];
  return {
    prop: "ssd_excess_m",
    unit: "m",
    stops: [
      [Math.round(q(0.02)), "#2166ac"],
      [Math.round(q(0.35)), "#67a9cf"],
      [0, "#f7f2e8"],
      [Math.round(q(0.65)), "#f0a202"],
      [Math.round(q(0.98)), "#d1382f"],
    ],
  };
}

// non-negative, unbounded-range properties (traffic volume, population
// density), no natural zero-crossing like the physics residual, so a
// plain low-to-high percentile ramp instead of a diverging one.
function computeSequentialStops(geojson, prop, unit) {
  const vals = geojson.features.map((f) => f.properties[prop]).filter((v) => v != null).sort((a, b) => a - b);
  const q = (p) => vals[Math.floor(p * (vals.length - 1))];
  return {
    prop,
    unit,
    stops: [
      [Math.round(q(0.05)), "#2166ac"],
      [Math.round(q(0.35)), "#67a9cf"],
      [Math.round(q(0.55)), "#f7f2e8"],
      [Math.round(q(0.8)), "#f0a202"],
      [Math.round(q(0.98)), "#d1382f"],
    ],
  };
}

const LAYER_META = {
  sss: { stops: () => ({ prop: "SSS", unit: "", stops: SSS_STOPS }), title: "Speed Safety Score" },
  physics: { stops: () => PHYSICS_STOPS, title: "Stopping-Distance Excess" },
  traffic: { stops: () => TRAFFIC_STOPS, title: "Traffic Volume (weighted sample)" },
  foottraffic: { stops: () => FOOTTRAFFIC_STOPS, title: "Foot Traffic (population density proxy)" },
};

function applyLayerStyle() {
  if (!map.getLayer("segments")) return;
  const meta = LAYER_META[currentLayer];
  const stops = meta.stops();
  map.setPaintProperty("segments", "line-color", colorExpr(stops));
  buildLegend(stops, meta.title);
}

function rankedItemBody(r) {
  if (currentAudience === "technical") {
    const reasons = [];
    if (r.ssgPctile > 90) reasons.push(`<b>Safe System violation</b>, ${r.ssgPctile}th pctile`);
    if (r.osrPctile > 90) reasons.push(`<b>${r.osr >= 0 ? "+" : ""}${r.osr} km/h</b> over predicted operating speed`);
    if (r.outlierPctile > 90) reasons.push(`<b>peer outlier</b>, ${r.outlierPctile}th pctile`);
    const reasonStr = reasons.length ? reasons.join(" · ") : "elevated across multiple components";
    return `posted ${r.speedLimit} km/h, observed ${r.f85} km/h · ${r.ssdExcess >= 0 ? "+" : ""}${r.ssdExcess}m stopping distance<br>${reasonStr}`;
  }
  const narrative = policyNarrative({ ssgPctile: r.ssgPctile, osrPctile: r.osrPctile, ssgRatio: r.ssgRatio, osr: r.osr });
  return `Posted ${r.speedLimit} km/h, actually driven ~${r.f85} km/h.<br>${narrative} ${vueBadge(r.vueScore)}`;
}

function renderRankedList(ranked) {
  const el = document.getElementById("ranked-list");
  el.innerHTML = ranked
    .map((r, i) => {
      return `
      <li class="ranked-item" data-lon="${r.lon}" data-lat="${r.lat}">
        <div class="ranked-item-top">
          <span><span class="ranked-rank">#${i + 1}</span><span class="ranked-road">${r.roadClass}, ${r.landUse.toLowerCase()}</span></span>
          <span class="ranked-score">${r.sss}</span>
        </div>
        <span class="tag tag-class tag-class-${r.riskClass.toLowerCase()}">${r.riskClass.toUpperCase()}</span>
        <div class="ranked-reason">${rankedItemBody(r)}</div>
      </li>`;
    })
    .join("");

  el.querySelectorAll(".ranked-item").forEach((item) => {
    item.addEventListener("click", () => {
      const lon = parseFloat(item.dataset.lon);
      const lat = parseFloat(item.dataset.lat);
      map.flyTo({ center: [lon, lat], zoom: 13, duration: 1200 });
      new maplibregl.Popup({ offset: 8 })
        .setLngLat([lon, lat])
        .setHTML(`<div class="popup-title">Priority Segment</div><div class="popup-row"><span class="k">Location</span><span>${lat.toFixed(3)}, ${lon.toFixed(3)}</span></div>`)
        .addTo(map);
    });
  });
}

async function renderCountry(country) {
  const { geojson, ranked, jurisdictions, pois } = await loadCountry(country);
  PHYSICS_STOPS = computePhysicsStops(geojson);
  TRAFFIC_STOPS = computeSequentialStops(geojson, "WeightedSample", "");
  FOOTTRAFFIC_STOPS = computeSequentialStops(geojson, "pop_density", "/km²");

  const total = geojson.features.length;
  const flagged = geojson.features.filter((f) => f.properties.is_significant).length;
  document.getElementById("stat-total").textContent = total.toLocaleString();
  document.getElementById("stat-flagged").textContent = flagged.toLocaleString();

  if (map.getSource("jurisdictions")) {
    map.getSource("jurisdictions").setData(jurisdictions);
  } else {
    map.addSource("jurisdictions", { type: "geojson", data: jurisdictions });
    map.addLayer({
      id: "jurisdictions-fill",
      type: "fill",
      source: "jurisdictions",
      layout: { visibility: "none" },
      paint: {
        "fill-color": colorExpr({ prop: "flagged_pct", stops: JURISDICTION_STOPS }),
        "fill-opacity": 0.45,
      },
    });
    map.addLayer({
      id: "jurisdictions-line",
      type: "line",
      source: "jurisdictions",
      layout: { visibility: "none" },
      paint: { "line-color": "#000", "line-opacity": 0.25, "line-width": 1 },
    });
    map.on("click", "jurisdictions-fill", (e) => {
      const p = e.features[0].properties;
      new maplibregl.Popup({ offset: 8 })
        .setLngLat(e.lngLat)
        .setHTML(`
          <div class="popup-title">${p.jurisdiction}</div>
          <div class="popup-row"><span class="k">Segments</span><span>${Math.round(p.total_segments).toLocaleString()}</span></div>
          <div class="popup-row"><span class="k">Flagged speed-unsafe</span><span>${Math.round(p.flagged_segments)} (${p.flagged_pct}%)</span></div>
          <div class="popup-row"><span class="k">Mean SSS</span><span>${p.mean_sss}</span></div>
        `)
        .addTo(map);
    });
    map.on("mouseenter", "jurisdictions-fill", () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", "jurisdictions-fill", () => (map.getCanvas().style.cursor = ""));
  }

  if (map.getSource("segments")) {
    map.getSource("segments").setData(geojson);
  } else {
    map.addSource("segments", { type: "geojson", data: geojson });
    map.addLayer({
      id: "segments",
      type: "line",
      source: "segments",
      paint: {
        "line-width": ["case", ["get", "is_significant"], 3.5, 1.4],
        "line-opacity": ["case", ["get", "is_significant"], 0.95, 0.55],
        "line-color": colorExpr({ prop: "SSS", stops: SSS_STOPS }),
      },
    });

    map.on("click", "segments", (e) => {
      const p = e.features[0].properties;
      const flagBadge = p.is_significant ? '<div class="popup-flag">FLAGGED SPEED-UNSAFE</div>' : "";
      const body =
        currentAudience === "technical"
          ? `
          <div class="popup-row"><span class="k">Posted limit</span><span>${p.SpeedLimit} km/h</span></div>
          <div class="popup-row"><span class="k">Observed 85th pct</span><span>${p.F85thPercentileSpeed} km/h</span></div>
          <div class="popup-row"><span class="k">Speed Safety Score</span><span>${p.SSS}</span></div>
          <div class="popup-row"><span class="k">Stopping-dist excess</span><span>${p.ssd_excess_m >= 0 ? "+" : ""}${p.ssd_excess_m} m</span></div>
        `
          : `
          <div class="popup-row"><span class="k">Posted limit</span><span>${p.SpeedLimit} km/h</span></div>
          <div class="popup-row"><span class="k">Actual speed</span><span>~${p.F85thPercentileSpeed} km/h</span></div>
          <p style="max-width: 220px; margin: 8px 0 0; font-family: var(--font-body); font-size: 11.5px; line-height: 1.5;">${policyNarrative({ ssgPctile: p.ssg_pctile, osrPctile: p.osr_pctile, ssgRatio: p.SSG_risk_ratio, osr: p.OSR })} ${vueBadge(p.vue_score)}</p>
        `;
      new maplibregl.Popup({ offset: 8 })
        .setLngLat(e.lngLat)
        .setHTML(`<div class="popup-title">${p.RoadClass}, ${p.LandUse.toLowerCase()}</div>${body}${flagBadge}`)
        .addTo(map);
    });
    map.on("mouseenter", "segments", () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", "segments", () => (map.getCanvas().style.cursor = ""));
  }

  if (map.getSource("pois")) {
    map.getSource("pois").setData(pois);
  } else {
    map.addSource("pois", { type: "geojson", data: pois });
    map.addLayer({
      id: "pois-icons",
      type: "circle",
      source: "pois",
      layout: { visibility: "none" },
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 6, 2.5, 12, 6],
        "circle-color": ["match", ["get", "category"], "school", POI_COLOR.school, "hospital", POI_COLOR.hospital, "market", POI_COLOR.market, POI_COLOR.other],
        "circle-stroke-width": 1,
        "circle-stroke-color": "#fff",
      },
    });
    map.on("click", "pois-icons", (e) => {
      const p = e.features[0].properties;
      new maplibregl.Popup({ offset: 8 })
        .setLngLat(e.lngLat)
        .setHTML(`<div class="popup-title">${POI_LABEL[p.category] || p.category}</div>${p.name ? `<div class="popup-row"><span>${p.name}</span></div>` : ""}`)
        .addTo(map);
    });
  }

  applyLayerStyle();
  renderRankedList(ranked);
}

function initControls() {
  document.querySelectorAll("#country-switch .ctl-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#country-switch .ctl-btn").forEach((b) => b.classList.remove("is-active"));
      btn.classList.add("is-active");
      currentCountry = btn.dataset.country;
      const c = COUNTRIES[currentCountry];
      map.flyTo({ center: c.center, zoom: c.zoom, duration: 1400 });
      renderCountry(currentCountry);
    });
  });

  document.querySelectorAll("#layer-switch .ctl-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#layer-switch .ctl-btn").forEach((b) => b.classList.remove("is-active"));
      btn.classList.add("is-active");
      currentLayer = btn.dataset.layer;
      applyLayerStyle();
    });
  });

  document.querySelectorAll("#overlay-switch .ctl-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      btn.classList.toggle("is-active");
      const layerIds = btn.dataset.overlay === "jurisdictions" ? ["jurisdictions-fill", "jurisdictions-line"] : ["pois-icons"];
      const visible = btn.classList.contains("is-active");
      layerIds.forEach((id) => {
        if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
      });
      if (btn.dataset.overlay === "pois") {
        document.getElementById("poi-legend").hidden = !visible;
      }
    });
  });

  document.querySelectorAll("#audience-switch .ctl-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#audience-switch .ctl-btn").forEach((b) => b.classList.remove("is-active"));
      btn.classList.add("is-active");
      currentAudience = btn.dataset.audience;
      if (dataCache[currentCountry]) renderRankedList(dataCache[currentCountry].ranked);
    });
  });

  document.getElementById("theme-toggle").addEventListener("click", () => {
    currentTheme = currentTheme === "light" ? "dark" : "light";
    applyTheme();
  });
}

function applyTheme() {
  document.documentElement.setAttribute("data-theme", currentTheme);
  localStorage.setItem("roadsense-theme", currentTheme);
  if (map && map.getLayer("carto-light")) {
    map.setLayoutProperty("carto-light", "visibility", currentTheme === "light" ? "visible" : "none");
    map.setLayoutProperty("carto-dark", "visibility", currentTheme === "dark" ? "visible" : "none");
  }
}

function init() {
  applyTheme();
  const c = COUNTRIES[currentCountry];
  map = new maplibregl.Map({
    container: "map",
    style: BASE_STYLE,
    center: c.center,
    zoom: c.zoom,
    attributionControl: { compact: true },
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");

  map.on("load", () => {
    applyTheme();
    renderCountry(currentCountry);
  });

  initControls();
}

init();
