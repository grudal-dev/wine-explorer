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
  const familyBox = document.getElementById("mol-family");
  const wikiBox = document.getElementById("mol-wikidata");
  const columns = root.querySelectorAll(".mol-columns [data-col]");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const C = {
    ink: "#23262F", ink2: "#5B5F69", paper: "#F8F8F4", rule: "#C9C9BF",
    molecule: "#2E6E6A", rouge: "#6B1730", blanc: "#D9C36A", rose: "#E59A8E",
    grape: "#7F9248", style: "#3B5878", color: "#8DA2BA", aroma: "#C99A3D", universal: "#B9B9AF",
    garnet: "#7A1F3D",
  };
  const _ = window.gettext || ((s) => s);
  const plural = (one, many, n) => (n > 1 ? many : one).replace("%s", n);
  const TYPE_LABEL = {
    profile: _("Revenir à ce vin"), molecule: _("Revenir à cette molécule"), source: _("Revenir à cet élément naturel"),
  };

  function moleculeLabel(n) {
    const odor = n.data("odor");
    return odor && odor.toLowerCase() !== n.data("label").toLowerCase() ? `${n.data("label")}\n${odor}` : n.data("label");
  }

  const state = { start: "", trail: [], common: false, family: true, wikidata: true };
  const query = () => `${state.common ? "&commun=1" : ""}${state.family ? "" : "&famille=0"}${state.wikidata ? "" : "&wikidata=0"}`;

  const cy = cytoscape({
    container: document.getElementById("mol-cy"),
    minZoom: 0.25, maxZoom: 2.5, wheelSensitivity: 0.25, boxSelectionEnabled: false, autoungrabify: true,
    style: [
      { selector: "node", style: {
        "label": "data(label)", "font-family": "Inter, system-ui, sans-serif", "font-size": 13.5, "color": C.ink,
        "text-valign": "center", "text-wrap": "wrap", "text-max-width": 170, "line-height": 1.25,
        "text-background-color": "#F8F8F4", "text-background-opacity": 0.92, "text-background-padding": 3,
        "text-background-shape": "roundrectangle",
        "width": 18, "height": 18, "border-width": 0,
        "transition-property": "opacity, border-width", "transition-duration": "160ms",
      }},
      { selector: "node[layer = 0]", style: { "text-halign": "left", "text-margin-x": -9 }},
      { selector: "node[layer = 2]", style: { "text-halign": "right", "text-margin-x": 9 }},
      { selector: "node[type='profile']", style: { "shape": "ellipse", "width": 22, "height": 22, "font-weight": 500,
        "border-width": 2, "border-color": C.ink, "background-color": C.rouge }},
      { selector: "node[type='profile'][wine='blanc']", style: { "background-color": C.blanc }},
      { selector: "node[type='profile'][wine='rose']", style: { "background-color": C.rose }},
      // Une molécule est une étiquette pleine : son nom et, dessous, ce qu'elle sent.
      { selector: "node[type='molecule']", style: { "shape": "round-rectangle", "label": moleculeLabel,
        "width": "label", "height": "label", "padding": "9px", "background-color": C.molecule,
        "color": "#fff", "font-weight": 500, "font-size": 13, "text-background-opacity": 0,
        "text-halign": "center", "text-margin-x": 0, "text-max-width": 190 }},
      { selector: "node[type='molecule'][tier='family']", style: { "background-color": "#5B8A86" }},
      { selector: "node[type='molecule'][tier='universal'], node[type='molecule'][?universal]", style: {
        "background-color": "#D3E2E0", "color": "#27514E", "font-weight": 400 }},
      { selector: "node[type='source']", style: { "shape": "ellipse", "width": 14, "height": 14,
        "background-color": "data(hue)" }},
      { selector: "node[type='source'][?imported]", style: { "background-opacity": 0.35, "border-width": 1.5,
        "border-style": "dashed", "border-color": "#56662D" }},
      { selector: "node[?root]", style: { "font-size": 16, "font-weight": 600, "border-width": 3, "border-color": C.garnet, "z-index": 5 }},
      { selector: "node[?root][type='profile'], node[?root][type='source']", style: { "width": 34, "height": 34 }},
      { selector: "node[?root][type='molecule']", style: { "font-size": 15, "padding": "12px" }},
      { selector: "node.compact[type='molecule']", style: { "shape": "hexagon", "label": "data(label)", "width": 26, "height": 23,
        "padding": "0px", "color": C.ink, "font-weight": 600, "font-size": 12, "text-valign": "bottom", "text-margin-y": 5,
        "text-max-width": 150, "text-background-opacity": 0.9 }},
      { selector: "node.compact", style: { "font-size": 12 }},
      { selector: "node.compact[?root]", style: { "font-size": 15 }},
      { selector: "edge", style: {
        "curve-style": "unbundled-bezier", "control-point-distances": [0], "control-point-weights": [0.5],
        "width": 1.4, "line-color": C.rule, "opacity": 0.9,
        "transition-property": "opacity, line-color, width", "transition-duration": "160ms",
      }},
      { selector: "edge[kind='contains']", style: { "width": "mapData(strength, 1, 3, 1.6, 5.5)" }},
      { selector: "edge[basis='grape']", style: { "line-color": C.grape }},
      { selector: "edge[basis='style']", style: { "line-color": C.style }},
      { selector: "edge[basis='color']", style: { "line-color": C.color }},
      { selector: "edge[basis='aroma']", style: { "line-color": C.aroma }},
      { selector: "edge[basis='universal']", style: { "line-color": C.universal, "line-style": "dashed" }},
      { selector: "edge[basis='family']", style: { "line-color": "#D9C08E", "line-style": "dotted", "width": 1.8 }},
      { selector: "edge[kind='found_in']", style: { "line-color": "#B9CCCA", "width": 1.2 }},
      { selector: "edge[kind='found_in'][tier='imported']", style: { "line-style": "dashed", "opacity": 0.6 }},
      { selector: ".faded", style: { "opacity": 0.12, "text-opacity": 0.25 }},
      { selector: "node.hl", style: { "border-width": 2, "border-color": C.ink }},
      { selector: "edge.hl", style: { "opacity": 1, "z-index": 9 }},
      { selector: "edge.hl[kind='found_in']", style: { "line-color": C.molecule, "width": 1.8 }},
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
    // Téléphone : même dessin qu'avant (hexagone, nom dessous), les étiquettes pleines y seraient trop larges.
    cy.nodes().toggleClass("compact", W < 640);
    const span = Math.max(W, 760);
    colX = [Math.max(span * 0.2, 190), span * 0.5, Math.min(span * 0.8, span - 190)];
    const layers = [[], [], []];
    cy.nodes().forEach((n) => layers[n.data("layer")].push(n));
    const top = 64;
    const usable = Math.max(H - top - 36, 200);
    const positions = {};
    let overflow = W < 760;
    layers.forEach((nodes, i) => {
      if (i !== 1 && layers[1].length) {
        const rank = new Map(layers[1].map((m, k) => [m.id(), k]));
        nodes.sort((a, b) => meanRank(a, rank) - meanRank(b, rank));
      }
      const ideal = i === 1 ? 70 : 44;
      // Un libellé long passe sur deux lignes : on laisse plus de place pour qu'il ne touche pas le voisin.
      const wraps = nodes.some((n) => (n.data("label") || "").length > 22);
      const floor = i === 1 ? 60 : wraps ? 36 : 26;
      const gap = nodes.length > 1 ? Math.max(Math.min(ideal, usable / (nodes.length - 1)), floor) : 0;
      if (gap * (nodes.length - 1) > usable) overflow = true;
      const h = (nodes.length - 1) * gap;
      nodes.forEach((n, k) => { positions[n.id()] = { x: colX[i], y: top + usable / 2 + k * gap - h / 2 }; });
    });
    run(positions, overflow);
  }

  function run(positions, fit) {
    cy.zoom(1);
    cy.pan({ x: 0, y: 0 });
    cy.layout({
      name: "preset", positions: (n) => positions[n.id()], fit, padding: 50,
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
    stats.textContent = _("Chargement…");
    let data;
    try {
      data = await Combo.getJSON(`${API}?kind=${kind}&slug=${encodeURIComponent(slug)}${query()}`);
    } catch (err) {
      stats.textContent = _("Impossible de charger ce graphe.");
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
    renderSources(data.references || []);
    history.replaceState(null, "", `${location.pathname}?depart=${encodeURIComponent(id)}${query()}`);
    openPanel(id);
  }

  function renderStats(s, kind) {
    const parts = [];
    if (kind !== "profile") {
      parts.push(plural(_("%s vin"), _("%s vins"), s.profiles)
        + (s.truncated ? " " + _("(et %s autres)").replace("%s", s.truncated) : ""));
    }
    parts.push(plural(_("%s molécule"), _("%s molécules"), s.molecules));
    if (kind !== "source") parts.push(plural(_("%s élément naturel"), _("%s éléments naturels"), s.sources));
    let text = parts.join(", ") + ".";
    if (!s.molecules && kind === "profile") text = _("Aucune molécule spécifique pour ce vin dans nos sources.");
    if (s.hidden_common) text += " " + plural(_("%s lien masqué (socle commun ou familles)."), _("%s liens masqués (socle commun ou familles)."), s.hidden_common);
    else if (s.common && !state.common && kind === "profile") text += " " + _("Socle commun ajouté : ce vin a peu de molécules propres.");
    if (s.hidden_sources) text += " " + plural(_("%s élément naturel de plus dans les fiches."), _("%s éléments naturels de plus dans les fiches."), s.hidden_sources);
    stats.textContent = text;
  }

  // ── Sources du graphe affiché ──────────────────────────────────────────
  const sourcesEl = document.getElementById("mol-sources");
  function renderSources(refs) {
    sourcesEl.innerHTML = "";
    if (!refs.length) {
      sourcesEl.innerHTML = `<li class="muted">${_("Aucun lien sourcé dans cette vue.")}</li>`;
      return;
    }
    refs.forEach((r) => {
      const li = document.createElement("li");
      const head = document.createElement("span");
      head.textContent = `${r.authors}${r.year ? ` (${r.year})` : ""}. `;
      li.appendChild(head);
      const title = document.createElement(r.link ? "a" : "span");
      title.textContent = r.title;
      if (r.link) { title.href = r.link; title.target = "_blank"; title.rel = "noopener"; }
      li.appendChild(title);
      if (r.container) {
        const c = document.createElement("em");
        c.textContent = `. ${r.container}`;
        li.appendChild(c);
      }
      const n = document.createElement("span");
      n.className = "muted";
      n.textContent = " · " + plural(_("%s lien"), _("%s liens"), r.links);
      li.appendChild(n);
      sourcesEl.appendChild(li);
    });
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
      btn.title = TYPE_LABEL[t.kind];
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

  document.getElementById("mol-goto-sources").addEventListener("click", (e) => {
    e.preventDefault();
    // On fait défiler le seul panneau latéral, pas la page (sur mobile, la page elle-même).
    const panel = root.querySelector(".explorer__panel");
    const target = document.getElementById("graph-sources-title");
    const behavior = reduceMotion ? "auto" : "smooth";
    if (panel.scrollHeight > panel.clientHeight) panel.scrollTo({ top: target.offsetTop - panel.offsetTop - 12, behavior });
    else target.scrollIntoView({ behavior, block: "start" });
  });
  const molPanel = document.getElementById("mol-panel");
  molPanel.addEventListener("click", (e) => {
    const more = e.target.closest("[data-expand]");
    if (more && molPanel.contains(more)) {
      const text = more.closest(".mol-card__text");
      text.querySelector("[data-short]").hidden = true;
      text.querySelector("[data-full]").hidden = false;
      more.remove();
      return;
    }
    // On cherche le bouton dans le panneau seulement : #mol-explorer, plus haut, porte lui aussi
    // data-start (le vin de départ), et un clic sur du texte ramenait au vin par défaut.
    const b = e.target.closest("[data-start]");
    if (b && molPanel.contains(b)) { e.preventDefault(); load(b.dataset.start); }
  });
  root.querySelectorAll(".explorer__rail [data-start]").forEach((b) => b.addEventListener("click", () => load(b.dataset.start)));

  document.getElementById("mol-random").addEventListener("click", () => {
    if (!RANDOM.length) return;
    let pick;
    do { pick = RANDOM[Math.floor(Math.random() * RANDOM.length)]; } while (pick === state.start && RANDOM.length > 1);
    load(pick);
  });
  commonBox.addEventListener("change", () => { state.common = commonBox.checked; if (state.start) load(state.start, { push: false }); });
  familyBox.addEventListener("change", () => { state.family = familyBox.checked; if (state.start) load(state.start, { push: false }); });
  if (wikiBox) wikiBox.addEventListener("change", () => { state.wikidata = wikiBox.checked; if (state.start) load(state.start, { push: false }); });

  document.getElementById("mol-fit").addEventListener("click", () => layoutColumns());
  window.addEventListener("resize", () => { clearTimeout(window.__molResize); window.__molResize = setTimeout(layoutColumns, 200); });
  document.getElementById("mol-png").addEventListener("click", () => {
    const a = document.createElement("a");
    a.href = cy.png({ full: true, scale: 2, bg: "#F8F8F4" });
    a.download = `wine-explorer-molecules-${(state.start.split(":")[1] || "graphe")}.png`;
    a.click();
  });

  const searchInput = document.getElementById("mol-search");
  // Deux champs, même comportement : celui du menu de gauche et celui au-dessus du graphe.
  [searchInput, document.getElementById("mol-search-top")].forEach((input) => {
    if (!input) return;
    const combo = Combo.attach(input, {
      source: async (q) => (await Combo.getJSON(`${SEARCH}?q=${encodeURIComponent(q)}`)).results,
      onSelect: (it) => { combo.clear(); load(it.id); },
    });
  });

  // Légende : ouverte sur grand écran, repliée sur téléphone où elle prendrait la moitié de la page.
  const legend = document.getElementById("mol-legend");
  if (legend && window.matchMedia("(min-width: 721px)").matches) legend.open = true;
  // La légende change la hauteur du graphe : on le remesure avant de placer les nœuds.
  cy.resize();
  if (legend) legend.addEventListener("toggle", () => { cy.resize(); if (state.start) layoutColumns(); });

  // Le cadre change de hauteur quand la ligne de résumé ou la légende passent sur plusieurs lignes :
  // on remesure, sinon le bas du graphe est coupé.
  if (window.ResizeObserver) {
    let lastH = 0;
    new ResizeObserver(() => {
      const h = cy.container().clientHeight;
      if (Math.abs(h - lastH) < 2) return;
      lastH = h;
      clearTimeout(window.__molResize);
      window.__molResize = setTimeout(() => { cy.resize(); if (state.start) layoutColumns(); }, 120);
    }).observe(cy.container());
  }

  // ── Démarrage ──────────────────────────────────────────────────────────
  const params = new URLSearchParams(location.search);
  state.common = params.get("commun") === "1";
  state.family = params.get("famille") !== "0";
  commonBox.checked = state.common;
  familyBox.checked = state.family;
  state.wikidata = params.get("wikidata") !== "0";
  if (wikiBox) wikiBox.checked = state.wikidata;
  const first = params.get("depart") || root.dataset.start;
  if (first) load(first);
  else stats.textContent = _("Choisissez un point de départ.");
})();
