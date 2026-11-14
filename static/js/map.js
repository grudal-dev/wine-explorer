/* Carte des goûts : projection 2D des vecteurs appris, voisins au clic, fiche HTMX. */
(function () {
  "use strict";

  const root = document.getElementById("taste-map");
  if (!root || !window.cytoscape) return;
  const _ = window.gettext || ((s) => s);

  const API = root.dataset.api;
  const NEIGHBOURS = root.dataset.neighbours;
  const PANEL = root.dataset.panel;
  const form = document.getElementById("map-form");
  const stats = document.getElementById("map-stats");
  const legend = document.getElementById("map-legend");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const SIZE = 1400;

  const WINE = { rouge: "#6B1730", blanc: "#D9C36A", rose: "#E59A8E" };
  const TYPE = { grape: "#56662D", aroma: "#B07D22", appellation: "#7A1F3D", region: "#3B5878", molecule: "#2E6E6A" };
  // Palette qualitative pour les régions (12 teintes distinctes sur fond clair).
  const PALETTE = ["#7A1F3D", "#3B5878", "#56662D", "#B07D22", "#2E6E6A", "#A4502A", "#6B4A8A", "#C2334D",
    "#4F7CAC", "#8A8D2F", "#B57BB0", "#5C5145", "#1F7A5A", "#C8782A"];
  const regionColor = {};
  let regionNames = {};

  const cy = cytoscape({
    container: document.getElementById("map-cy"),
    minZoom: 0.3, maxZoom: 6, boxSelectionEnabled: false, autoungrabify: true,
    style: [
      { selector: "node", style: {
        "label": "data(label)", "font-family": "Inter, system-ui, sans-serif", "font-size": 10,
        "color": "#23262F", "text-valign": "bottom", "text-margin-y": 3, "min-zoomed-font-size": 9,
        "text-background-color": "#F8F8F4", "text-background-opacity": 0.8, "text-background-padding": 1.5,
        "width": 12, "height": 12, "background-color": "data(color)", "border-width": 1, "border-color": "#23262F",
        "transition-property": "opacity", "transition-duration": "150ms",
      }},
      { selector: "node[type='profile']", style: { "width": 14, "height": 14, "border-width": 1.5 }},
      { selector: "node[type='grape']", style: { "shape": "diamond", "font-style": "italic" }},
      { selector: "node[type='aroma']", style: { "shape": "ellipse", "width": 9, "height": 9, "border-width": 0, "font-style": "italic" }},
      { selector: "node[type='appellation']", style: { "shape": "round-rectangle", "width": 9, "height": 9 }},
      { selector: "node[type='region']", style: { "shape": "round-rectangle", "width": 18, "height": 12, "font-weight": 600, "font-size": 12, "min-zoomed-font-size": 0 }},
      { selector: "node[type='molecule']", style: { "shape": "hexagon" }},
      { selector: ".dim", style: { "opacity": 0.15, "text-opacity": 0 }},
      { selector: ".off", style: { "display": "none" }},
      { selector: "node.near", style: { "min-zoomed-font-size": 0, "font-weight": 600, "z-index": 9 }},
      { selector: "node:selected", style: { "border-width": 4, "border-color": "#7A1F3D", "min-zoomed-font-size": 0,
        "font-weight": 600, "font-size": 11, "z-index": 10, "overlay-opacity": 0 }},
      { selector: "edge", style: { "width": "mapData(similarity, 0.5, 1, 1, 5)", "line-color": "#7A1F3D",
        "opacity": 0.55, "curve-style": "straight" }},
    ],
  });

  function nodeColor(n) {
    if (n.type !== "profile") return n.hue || TYPE[n.type] || "#23262F";
    if (form.color.value === "region") return regionColor[n.root] || "#8A8D94";
    return WINE[n.wine] || "#23262F";
  }

  function drawLegend() {
    legend.innerHTML = "";
    const entries = form.color.value === "region"
      ? Object.keys(regionColor).map((slug) => [regionColor[slug], regionNames[slug] || slug])
      : [[WINE.rouge, _("Rouge")], [WINE.blanc, _("Blanc")], [WINE.rose, _("Rosé")]];
    entries.forEach(([color, label]) => {
      const li = document.createElement("li");
      const dot = document.createElement("i");
      dot.style.background = color;
      li.append(dot, document.createTextNode(label));
      legend.appendChild(li);
    });
  }

  function applyFilters() {
    const fd = new FormData(form);
    const types = fd.getAll("types");
    const colors = fd.getAll("colors");
    const region = fd.get("region");
    let shown = 0;
    cy.batch(() => {
      cy.nodes().forEach((n) => {
        const d = n.data();
        let on = types.includes(d.type);
        if (on && d.type === "profile") {
          if (colors.length && !colors.includes(d.wine)) on = false;
          if (region && d.root !== region) on = false;
        }
        n.toggleClass("off", !on);
        n.data("color", nodeColor(d));
        if (on) shown += 1;
      });
    });
    stats.textContent = shown
      ? interpolate(_("%s points. Deux points proches se ressemblent."), [shown])
      : _("Rien à afficher avec ces filtres.");
    drawLegend();
  }

  function clearSelection() {
    cy.edges().remove();
    cy.nodes().removeClass("dim near");
  }

  async function select(id, { center = false } = {}) {
    let node = cy.getElementById(id);
    if (node.empty()) return;
    if (node.hasClass("off")) {
      // L'entité cherchée est d'un type masqué : on l'affiche.
      const cb = form.querySelector(`input[name='types'][value='${node.data("type")}']`);
      if (cb && !cb.checked) cb.checked = true;
      form.region.value = "";
      form.querySelectorAll("input[name='colors']").forEach((c) => { c.checked = false; });
      applyFilters();
      node = cy.getElementById(id);
    }
    clearSelection();
    cy.$(":selected").unselect();
    node.select();
    if (window.htmx) htmx.ajax("GET", PANEL.replace("X", encodeURIComponent(id)), { target: "#map-panel", swap: "innerHTML" });
    history.replaceState(null, "", `${location.pathname}?focus=${encodeURIComponent(id)}`);
    let data;
    try {
      data = await Combo.getJSON(`${NEIGHBOURS}?id=${encodeURIComponent(id)}`);
    } catch (err) {
      return;
    }
    if (!node.selected()) return; // une autre sélection est arrivée entre-temps
    cy.nodes().not(".off").addClass("dim");
    node.removeClass("dim");
    const group = cy.collection().union(node);
    data.neighbours.forEach((nb) => {
      const other = cy.getElementById(nb.id);
      if (other.empty() || other.hasClass("off")) return;
      other.removeClass("dim").addClass("near");
      cy.add({ group: "edges", data: { id: `nb-${nb.id}`, source: id, target: nb.id, similarity: nb.similarity } });
      group.merge(other);
    });
    if (center) {
      // On cadre le voisinage sans coller le nez dessus : au-delà de ×2,2 les libellés se chevauchent.
      cy.fit(group, 120);
      if (cy.zoom() > 2.2) cy.zoom({ level: 2.2, position: node.position() });
    }
  }

  cy.on("tap", "node", (e) => select(e.target.id()));
  cy.on("tap", (e) => { if (e.target === cy) { clearSelection(); cy.$(":selected").unselect(); } });
  cy.on("mouseover", "node", () => { cy.container().style.cursor = "pointer"; });
  cy.on("mouseout", "node", () => { cy.container().style.cursor = ""; });

  form.addEventListener("change", () => { clearSelection(); applyFilters(); });
  document.getElementById("map-fit").addEventListener("click", () =>
    cy.animate({ fit: { eles: cy.nodes().not(".off"), padding: 40 } }, { duration: reduceMotion ? 0 : 300 }));
  document.getElementById("map-png").addEventListener("click", () => {
    const a = document.createElement("a");
    a.href = cy.png({ full: true, scale: 2, bg: "#F8F8F4" });
    a.download = "sillage-carte-des-gouts.png";
    a.click();
  });
  document.getElementById("map-panel").addEventListener("click", (e) => {
    const b = e.target.closest("[data-map-select]");
    if (b) select(b.dataset.mapSelect, { center: true });
  });

  const searchInput = document.getElementById("map-search");
  let all = [];
  const fold = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const search = Combo.attach(searchInput, {
    source: async (q) => {
      const nq = fold(q);
      return all.filter((n) => fold(n.label).includes(nq))
        .sort((a, b) => fold(a.label).indexOf(nq) - fold(b.label).indexOf(nq) || a.label.length - b.label.length)
        .slice(0, 10).map((n) => ({ id: n.id, label: n.label, hint: n.typeLabel }));
    },
    onSelect: (it) => { search.clear(); select(it.id, { center: true }); },
  });

  async function start() {
    let data;
    try {
      data = await Combo.getJSON(API);
    } catch (err) {
      stats.textContent = _("Impossible de charger la carte.");
      return;
    }
    if (!data.nodes.length) return;
    const typeLabels = {};
    form.querySelectorAll("input[name='types']").forEach((cb) => { typeLabels[cb.value] = cb.parentElement.textContent.trim(); });
    regionNames = {};
    form.querySelectorAll("#map-region option").forEach((o) => { if (o.value) regionNames[o.value] = o.textContent; });
    [...new Set(data.nodes.filter((n) => n.type === "profile").map((n) => n.root))].sort()
      .forEach((slug, i) => { regionColor[slug] = PALETTE[i % PALETTE.length]; });
    all = data.nodes.map((n) => ({ id: n.id, label: n.label, typeLabel: typeLabels[n.type] || "" }));
    cy.add(data.nodes.map((n) => ({
      group: "nodes", data: { ...n, color: "#23262F" }, position: { x: n.x * SIZE, y: n.y * SIZE },
    })));
    applyFilters();
    cy.fit(cy.nodes().not(".off"), 40);
    if (root.dataset.focus) select(root.dataset.focus, { center: true });
  }

  start();
})();
