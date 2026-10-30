/* Graphe moléculaire : vin → molécules → éléments naturels, en trois colonnes. */
(function () {
  "use strict";

  const root = document.getElementById("mol-explorer");
  if (!root || !window.cytoscape) return;

  const API = root.dataset.api;
  const SEARCH = root.dataset.search;
  const PANEL = root.dataset.panel; // .../fiche/X/
  const RANDOM = (root.dataset.random || "").split(",").filter(Boolean);
  const stats = document.getElementById("mol-stats");
  const trailEl = document.getElementById("mol-trail");
  const commonBox = document.getElementById("mol-common");
  const columns = root.querySelectorAll(".mol-columns [data-col]");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const C = {
    ink: "#23262F", ink2: "#5B5F69", paper: "#F8F8F4", rule: "#C9C9BF",
    molecule: "#2E6E6A", rouge: "#6B1730", blanc: "#D9C36A", rose: "#E59A8E",
    grape: "#7F9248", style: "#3B5878", color: "#8DA2BA", aroma: "#C99A3D", universal: "#B9B9AF",
    garnet: "#7A1F3D",
  };
    const TYPE_LABEL = { profile: "vin", molecule: "molécule", source: "élément naturel" };

  const state = { start: "", trail: [], common: false };

  const cy = cytoscape({
    container: document.getElementById("mol-cy"),
    minZoom: 0.25, maxZoom: 2.5, wheelSensitivity: 0.25, boxSelectionEnabled: false, autoungrabify: true,
    style: [
      { selector: "node", style: {
        "label": "data(label)", "font-family": "Inter, system-ui, sans-serif", "font-size": 12, "color": C.ink,
        "text-valign": "center", "text-wrap": "wrap", "text-max-width": 150,
        "text-background-color": "#F8F8F4", "text-background-opacity": 0.9, "text-background-padding": 2,
        "width": 18, "height": 18, "border-width": 0,
        "transition-property": "opacity, border-width", "transition-duration": "160ms",
      }},
      { selector: "node[layer = 0]", style: { "text-halign": "left", "text-margin-x": -8 }},
      { selector: "node[layer = 2]", style: { "text-halign": "right", "text-margin-x": 8 }},
      { selector: "node[type='profile']", style: { "shape": "ellipse", "width": 20, "height": 20,
        "border-width": 2, "border-color": C.ink, "background-color": C.rouge }},
      { selector: "node[type='profile'][wine='blanc']", style: { "background-color": C.blanc }},
      { selector: "node[type='profile'][wine='rose']", style: { "background-color": C.rose }},
      { selector: "node[type='molecule']", style: { "shape": "hexagon", "width": 26, "height": 23,
        "background-color": C.molecule, "text-valign": "bottom", "text-margin-y": 5, "font-weight": 600 }},
      { selector: "node[type='molecule'][?universal]", style: { "background-color": "#7FA3A0" }},
      { selector: "node[type='source']", style: { "shape": "round-rectangle", "width": 16, "height": 16,
        "background-color": "data(hue)", "font-style": "italic" }},
      { selector: "node[?root]", style: { "width": 34, "height": 34, "font-size": 15, "font-weight": 600,
        "border-width": 3, "border-color": C.garnet, "z-index": 5 }},
      { selector: "node[type='molecule'][?root]", style: { "width": 40, "height": 35 }},
      { selector: "edge", style: {
        "curve-style": "unbundled-bezier", "control-point-distances": [0], "control-point-weights": [0.5],
        "width": 1.4, "line-color": C.rule, "opacity": 0.85,
        "transition-property": "opacity, line-color, width", "transition-duration": "160ms",
      }},
      { selector: "edge[kind='contains']", style: { "width": "mapData(strength, 1, 3, 1.4, 5)" }},
      { selector: "edge[basis='grape']", style: { "line-color": C.grape }},
      { selector: "edge[basis='style']", style: { "line-color": C.style }},
      { selector: "edge[basis='color']", style: { "line-color": C.color }},
      { selector: "edge[basis='aroma']", style: { "line-color": C.aroma }},
      { selector: "edge[basis='universal']", style: { "line-color": C.universal, "line-style": "dashed" }},
      { selector: "edge[kind='found_in']", style: { "line-color": "#9DB8B5" }},
      { selector: ".faded", style: { "opacity": 0.12, "text-opacity": 0.25 }},
      { selector: "node.hl", style: { "border-width": 3, "border-color": C.ink }},
      { selector: "edge.hl", style: { "opacity": 1, "z-index": 9 }},
      { selector: "node:selected", style: { "border-width": 4, "border-color": C.garnet, "overlay-opacity": 0 }},
    ],
  });

  // ── Disposition en colonnes ─────────────────────────────────────────────
  // Les colonnes occupent la largeur du cadre ; l'espacement vertical s'adapte au nombre de
  // nœuds pour garder des libellés lisibles (zoom 1) tant que tout tient à l'écran.
  let colX = [0, 420, 840];
  function layoutColumns() {
    const W = cy.width();
    const H = cy.height();
    // Sous 760 px, on dessine sur une largeur virtuelle puis on ajuste le zoom.
    const span = Math.max(W, 760);
    colX = [Math.max(span * 0.22, 190), span * 0.5, Math.min(span * 0.78, span - 190)];
    const layers = [[], [], []];
    cy.nodes().forEach((n) => layers[n.data("layer")].push(n));
    const top = 70;
    const usable = Math.max(H - top - 70, 200);
    const positions = {};
    let overflow = W < 760;
    layers.forEach((nodes, i) => {
      if (i !== 1 && layers[1].length) {
        const rank = new Map(layers[1].map((m, k) => [m.id(), k]));
        nodes.sort((a, b) => meanRank(a, rank) - meanRank(b, rank));
      }
      const ideal = i === 1 ? 74 : 46;
      const gap = nodes.length > 1 ? Math.max(Math.min(ideal, usable / (nodes.length - 1)), i === 1 ? 40 : 24) : 0;
      if (gap * (nodes.length - 1) > usable) overflow = true;
      const h = (nodes.length - 1) * gap;
      nodes.forEach((n, k) => { positions[n.id()] = { x: colX[i], y: top + usable / 2 + k * gap - h / 2 }; });
    });
    cy.zoom(1);
    cy.pan({ x: 0, y: 0 });
    cy.layout({
      name: "preset", positions: (n) => positions[n.id()], fit: overflow, padding: 50,
      animate: !reduceMotion, animationDuration: 380,
    }).run();
    placeColumnLabels();
  }
  function meanRank(n, rank) {
    const r = n.neighborhood("node").map((m) => rank.get(m.id())).filter((v) => v !== undefined);
    return r.length ? r.reduce((a, b) => a + b, 0) / r.length : 0;
  }

  function placeColumnLabels() {
    const pan = cy.pan();
    const z = cy.zoom();
    const present = new Set(cy.nodes().map((n) => n.data("layer")));
    columns.forEach((el) => {
      const i = +el.dataset.col;
      el.style.left = `${colX[i] * z + pan.x}px`;
      el.hidden = !present.has(i);
    });
  }
  cy.on("viewport", placeColumnLabels);

  // ── Chargement ─────────────────────────────────────────────────────────
  let seq = 0;
  async function load(id, { push = true } = {}) {
    const [kind, slug] = id.split(":");
    const mine = ++seq;
    stats.textContent = "Chargement…";
    let data;
    try {
      data = await Combo.getJSON(`${API}?kind=${kind}&slug=${encodeURIComponent(slug)}${state.common ? "&commun=1" : ""}`);
    } catch (err) {
      stats.textContent = "Impossible de charger ce graphe.";
      return;
    }
    if (mine !== seq) return;
    state.start = id;
    cy.elements().remove();
    cy.add(data.elements);
    layoutColumns();
    if (!reduceMotion) {
      cy.nodes().forEach((n) => {
        n.style("opacity", 0);
        n.delay(n.data("layer") * 140 + 40).animate({ style: { opacity: 1 } }, { duration: 260 });
      });
    }
    const rootNode = cy.getElementById(id);
    const label = rootNode.nonempty() ? rootNode.data("label") : slug;
    if (push) pushTrail(id, label, kind);
    renderStats(data.stats, kind);
    history.replaceState(null, "", `${location.pathname}?depart=${encodeURIComponent(id)}${state.common ? "&commun=1" : ""}`);
    openPanel(id);
  }

  function renderStats(s, kind) {
    const parts = [];
    if (kind !== "profile") parts.push(`${s.profiles} vin${s.profiles > 1 ? "s" : ""}${s.truncated ? ` (et ${s.truncated} autres)` : ""}`);
    parts.push(`${s.molecules} molécule${s.molecules > 1 ? "s" : ""}`);
    if (kind !== "source") parts.push(`${s.sources} élément${s.sources > 1 ? "s" : ""} naturel${s.sources > 1 ? "s" : ""}`);
    let text = parts.join(", ") + ".";
    if (!s.molecules && kind === "profile") text = "Aucune molécule spécifique pour ce vin dans nos sources.";
    if (s.hidden_common && !state.common) text += ` ${s.hidden_common} lien${s.hidden_common > 1 ? "s" : ""} du socle commun masqué${s.hidden_common > 1 ? "s" : ""}.`;
    stats.textContent = text;
  }

  // ── Parcours (fil d'Ariane du jeu) ─────────────────────────────────────
  function pushTrail(id, label, kind) {
    const at = state.trail.findIndex((t) => t.id === id);
    if (at >= 0) state.trail = state.trail.slice(0, at + 1);
    else state.trail.push({ id, label, kind });
    if (state.trail.length > 7) state.trail = state.trail.slice(-7);
    trailEl.innerHTML = "";
    state.trail.forEach((t, i) => {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = `tag tag--${t.kind}`;
      btn.textContent = t.label;
      btn.title = `Revenir à ce ${TYPE_LABEL[t.kind]}`;
      if (i === state.trail.length - 1) btn.setAttribute("aria-current", "step");
      btn.addEventListener("click", () => load(t.id));
      li.appendChild(btn);
      trailEl.appendChild(li);
    });
  }

  // ── Interaction ────────────────────────────────────────────────────────
  function highlight(node) {
    // Chaîne complète : un vin éclaire ses molécules et leurs sources, un élément naturel
    // ses molécules et les vins qui les contiennent (arêtes orientées vin → molécule → nature).
    const type = node.data("type");
    let chain = node.closedNeighborhood();
    if (type === "profile") chain = node.union(node.successors());
    else if (type === "source") chain = node.union(node.predecessors());
    cy.elements().addClass("faded").removeClass("hl");
    chain.removeClass("faded").addClass("hl");
  }
  function clearHighlight() { cy.elements().removeClass("faded hl"); }

  function openPanel(id) {
    const rootProfile = state.start.startsWith("profile:") ? state.start.split(":")[1] : "";
    let url = PANEL.replace("X", encodeURIComponent(id));
    if (id.startsWith("molecule:") && rootProfile) url += `?vin=${encodeURIComponent(rootProfile)}`;
    if (window.htmx) htmx.ajax("GET", url, { target: "#mol-panel", swap: "innerHTML" });
  }

  cy.on("tap", "node", (e) => { highlight(e.target); openPanel(e.target.id()); });
  cy.on("dbltap", "node", (e) => load(e.target.id()));
  cy.on("tap", (e) => { if (e.target === cy) clearHighlight(); });
  cy.on("mouseover", "node", (e) => { cy.container().style.cursor = "pointer"; if (!cy.$(":selected").length) highlight(e.target); });
  cy.on("mouseout", "node", () => { cy.container().style.cursor = ""; if (!cy.$(":selected").length) clearHighlight(); });

  document.getElementById("mol-panel").addEventListener("click", (e) => {
    const b = e.target.closest("[data-start]");
    if (b) { e.preventDefault(); load(b.dataset.start); }
  });
  root.querySelectorAll(".explorer__rail [data-start]").forEach((b) => b.addEventListener("click", () => load(b.dataset.start)));

  document.getElementById("mol-random").addEventListener("click", () => {
    if (!RANDOM.length) return;
    let pick;
    do { pick = RANDOM[Math.floor(Math.random() * RANDOM.length)]; } while (pick === state.start && RANDOM.length > 1);
    load(pick);
  });
  commonBox.addEventListener("change", () => { state.common = commonBox.checked; if (state.start) load(state.start, { push: false }); });

  document.getElementById("mol-fit").addEventListener("click", () => layoutColumns());
  window.addEventListener("resize", () => { clearTimeout(window.__molResize); window.__molResize = setTimeout(layoutColumns, 200); });
  document.getElementById("mol-png").addEventListener("click", () => {
    const a = document.createElement("a");
    a.href = cy.png({ full: true, scale: 2, bg: "#F8F8F4" });
    a.download = `terroirs-molecules-${(state.start.split(":")[1] || "graphe")}.png`;
    a.click();
  });

  const searchInput = document.getElementById("mol-search");
  const search = Combo.attach(searchInput, {
    source: async (q) => (await Combo.getJSON(`${SEARCH}?q=${encodeURIComponent(q)}`)).results,
    onSelect: (it) => { search.clear(); load(it.id); },
  });

  // ── Démarrage ──────────────────────────────────────────────────────────
  const params = new URLSearchParams(location.search);
  state.common = params.get("commun") === "1";
  commonBox.checked = state.common;
  const first = params.get("depart") || root.dataset.start;
  if (first) load(first);
  else stats.textContent = "Choisissez un point de départ.";
})();
