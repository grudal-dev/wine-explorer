/* Explorateur de graphe : Cytoscape + filtres + panneau HTMX + plus court chemin. */
(function () {
  "use strict";

  const root = document.getElementById("explorer");
  if (!root || !window.cytoscape) return;
  if (window.cytoscapeFcose) cytoscape.use(window.cytoscapeFcose);

  const API = root.dataset.api;
  const SEARCH = root.dataset.search;
  const PATH = root.dataset.path;
  const NODE = root.dataset.node; // .../noeud/X/
  const form = document.getElementById("graph-form");
  const stats = document.getElementById("graph-stats");
  const unfocusBtn = document.getElementById("btn-unfocus");
  const layoutSelect = document.getElementById("f-layout");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const COLORS = {
    region: "#3B5878", appellation: "#7A1F3D", grape: "#56662D",
    aroma: "#B07D22", family: "#8A6A3A", ink: "#23262F", rule: "#C9C9BF", molecule: "#2E6E6A",
    rouge: "#6B1730", blanc: "#D9C36A", rose: "#E59A8E",
  };
  const TYPE_LABELS = {
    region: "régions", appellation: "appellations", profile: "profils",
    grape: "cépages", aroma: "arômes", family: "familles", molecule: "molécules", source: "éléments naturels",
  };

  const state = { focus: root.dataset.focus || "", depth: 2, path: { a: null, b: null } };

  // ── Cytoscape ────────────────────────────────────────────────────────────
  const cy = cytoscape({
    container: document.getElementById("cy"),
    minZoom: 0.15,
    maxZoom: 3,
    style: [
      { selector: "node", style: {
        "label": "data(label)", "font-family": "Inter, system-ui, sans-serif", "font-size": 11,
        "color": COLORS.ink, "text-valign": "bottom", "text-margin-y": 4,
        "text-background-color": "#ECECE6", "text-background-opacity": 0.85, "text-background-padding": 2,
        "min-zoomed-font-size": 8, "width": "mapData(degree, 0, 30, 14, 46)", "height": "mapData(degree, 0, 30, 14, 46)",
        "background-color": COLORS.ink, "border-width": 0, "transition-property": "opacity", "transition-duration": "150ms",
      }},
      { selector: "node[type='region']", style: { "background-color": COLORS.region, "shape": "round-rectangle",
        "font-size": 13, "font-weight": 600, "min-zoomed-font-size": 0, "width": "mapData(degree, 0, 30, 26, 60)", "height": "mapData(degree, 0, 30, 18, 40)" }},
      { selector: "node[type='appellation']", style: { "background-color": COLORS.appellation }},
      { selector: "node[degree >= 7]", style: { "min-zoomed-font-size": 0, "font-weight": 600 }},
      { selector: "node[type='profile']", style: { "border-width": 2, "border-color": COLORS.ink,
        "width": 16, "height": 16, "font-size": 10 }},
      { selector: "node[type='profile'][wine='rouge']", style: { "background-color": COLORS.rouge }},
      { selector: "node[type='profile'][wine='blanc']", style: { "background-color": COLORS.blanc }},
      { selector: "node[type='profile'][wine='rose']", style: { "background-color": COLORS.rose }},
      { selector: "node[type='grape']", style: { "background-color": COLORS.grape, "shape": "diamond" }},
      { selector: "node[type='aroma']", style: { "background-color": "data(hue)", "font-style": "italic" }},
      { selector: "node[type='family']", style: { "background-color": "data(hue)", "shape": "hexagon",
        "width": 34, "height": 34, "font-size": 12, "font-weight": 600 }},
      { selector: "node[type='molecule']", style: { "background-color": COLORS.molecule, "shape": "hexagon",
        "width": "mapData(degree, 0, 30, 16, 40)", "height": "mapData(degree, 0, 30, 14, 35)" }},
      { selector: "node[type='source']", style: { "background-color": "data(hue)", "shape": "round-rectangle",
        "width": 14, "height": 14, "font-style": "italic" }},
      { selector: "node[type='source'][?imported]", style: { "background-opacity": 0.35, "border-width": 1.5,
        "border-style": "dashed", "border-color": "#56662D" }},
      { selector: "edge", style: {
        "width": 1, "line-color": COLORS.rule, "curve-style": "haystack", "haystack-radius": 0.4, "opacity": 0.75,
      }},
      { selector: "edge[kind='grape']", style: { "width": "mapData(weight, 0, 3, 1, 5)", "line-color": "#A7B38A" }},
      { selector: "edge[kind='aroma']", style: { "width": "mapData(weight, 1, 9, 1, 4)", "line-color": "#D8C49A" }},
      { selector: "edge[kind='part_of'], edge[kind='located_in']", style: { "line-color": "#9FB0C3" }},
      { selector: "edge[kind='molecule']", style: { "width": "mapData(weight, 1, 9, 1, 4)", "line-color": "#8FB5B1" }},
      { selector: "edge[kind='evokes']", style: { "line-color": "#D9C08E", "line-style": "dashed" }},
      { selector: "edge[kind='found_in']", style: { "line-color": "#A7B38A" }},
      { selector: ".faded", style: { "opacity": 0.12, "text-opacity": 0 }},
      { selector: "node.hl", style: { "border-width": 3, "border-color": COLORS.ink, "z-index": 10 }},
      { selector: "edge.hl", style: { "line-color": COLORS.ink, "opacity": 1, "z-index": 9 }},
      { selector: "node:selected", style: { "border-width": 4, "border-color": "#7A1F3D", "overlay-opacity": 0 }},
      { selector: "edge.path", style: { "line-color": "#7A1F3D", "width": 4, "opacity": 1, "z-index": 20,
        "curve-style": "bezier" }},
      { selector: "node.path", style: { "border-width": 3, "border-color": "#7A1F3D", "opacity": 1,
        "text-opacity": 1, "z-index": 21, "font-weight": 600, "min-zoomed-font-size": 0 }},
      { selector: "node.path-extra", style: { "border-style": "dashed", "width": 18, "height": 18 }},
    ],
  });

  function layoutOptions(name) {
    const base = { animate: !reduceMotion, animationDuration: 450, fit: true, padding: 40 };
    if (name === "fcose" && window.cytoscapeFcose) {
      return { ...base, name: "fcose", quality: "default", randomize: true, nodeRepulsion: 9000,
        idealEdgeLength: 70, edgeElasticity: 0.35, nodeSeparation: 80, packComponents: true };
    }
    if (name === "concentric") {
      const order = { region: 7, family: 6, appellation: 5, grape: 4, profile: 3, molecule: 2, aroma: 1, source: 0 };
      return { ...base, name: "concentric", minNodeSpacing: 12,
        concentric: (n) => order[n.data("type")] || 0, levelWidth: () => 1 };
    }
    if (name === "breadthfirst") {
      return { ...base, name: "breadthfirst", spacingFactor: 0.9, directed: false,
        roots: cy.nodes("[type='region'], [type='family'], [type='source']").filter((n) => n.degree() > 0) };
    }
    if (name === "fcose") return { ...base, name: "cose" };
    return { ...base, name };
  }

  function runLayout() {
    const layout = cy.layout(layoutOptions(layoutSelect.value));
    layout.run();
    return layout;
  }

  // ── Paramètres ↔ formulaire ↔ URL ───────────────────────────────────────
  function params() {
    const fd = new FormData(form);
    const p = new URLSearchParams();
    fd.getAll("types").forEach((v) => p.append("types", v));
    fd.getAll("colors").forEach((v) => p.append("colors", v));
    if (fd.get("region")) p.set("region", fd.get("region"));
    if (fd.get("price_max") && fd.get("price_max") !== "100") p.set("price_max", fd.get("price_max"));
    p.set("min_intensity", fd.get("min_intensity"));
    p.set("min_share", fd.get("min_share"));
    p.set("min_strength", fd.get("min_strength"));
    if (state.focus) { p.set("focus", state.focus); p.set("depth", state.depth); }
    return p;
  }

  function applyParams(p) {
    const types = p.getAll("types");
    form.querySelectorAll("input[name='types']").forEach((cb) => {
      cb.checked = types.length ? types.includes(cb.value) : ["region", "appellation", "grape"].includes(cb.value);
    });
    const colors = p.getAll("colors");
    form.querySelectorAll("input[name='colors']").forEach((cb) => { cb.checked = colors.includes(cb.value); });
    if (p.get("region")) form.region.value = p.get("region");
    if (p.get("price_max")) form.price_max.value = p.get("price_max");
    if (p.get("min_intensity")) form.min_intensity.value = p.get("min_intensity");
    if (p.get("min_share")) form.min_share.value = p.get("min_share");
    if (p.get("min_strength")) form.min_strength.value = p.get("min_strength");
    if (p.get("focus")) state.focus = p.get("focus");
    syncOutputs();
    syncPreset();
  }

  function syncOutputs() {
    const price = form.price_max.value;
    document.getElementById("f-price-out").textContent = price === "100" ? "sans limite" : `${price} €`;
    document.getElementById("f-int-out").textContent = form.min_intensity.value;
    document.getElementById("f-share-out").textContent = `${form.min_share.value} %`;
    document.getElementById("f-strength-out").textContent =
      { 1: "plausible", 2: "probable", 3: "marqueur établi" }[form.min_strength.value];
  }

  function syncPreset() {
    const types = [...form.querySelectorAll("input[name='types']:checked")].map((c) => c.value).sort().join(",");
    document.querySelectorAll("[data-preset]").forEach((b) => {
      b.setAttribute("aria-checked", b.dataset.types.split(",").sort().join(",") === types ? "true" : "false");
    });
  }

  // ── Chargement ───────────────────────────────────────────────────────────
  let loadSeq = 0;
  async function load({ keepSelection = false } = {}) {
    const p = params();
    history.replaceState(null, "", `${location.pathname}?${p}`);
    stats.textContent = "Chargement…";
    const mine = ++loadSeq;
    const data = await Combo.getJSON(`${API}?${p}`);
    if (mine !== loadSeq) return;
    cy.elements().remove();
    cy.add(data.elements);
    const parts = Object.entries(data.stats.by_type).filter(([, n]) => n)
      .map(([t, n]) => `${n} ${TYPE_LABELS[t]}`);
    stats.textContent = data.stats.nodes
      ? `${parts.join(", ")}, ${data.stats.edges} liens.`
      : "Aucun résultat avec ces filtres. Élargissez la sélection.";
    unfocusBtn.hidden = !state.focus;
    const layout = runLayout();
    if (state.focus) {
      const n = cy.getElementById(state.focus);
      if (n.nonempty()) { n.select(); highlight(n); openPanel(state.focus); }
    } else if (!keepSelection) {
      clearHighlight();
    }
    if (currentPath) layout.one("layoutstop", drawPath);
  }

  // ── Interaction ──────────────────────────────────────────────────────────
  function highlight(node) {
    const hood = node.closedNeighborhood();
    cy.elements().addClass("faded").removeClass("hl");
    hood.removeClass("faded");
    hood.edges().addClass("hl");
    node.addClass("hl");
  }
  function clearHighlight() { cy.elements().removeClass("faded hl"); }

  function openPanel(id) {
    const url = NODE.replace("X", encodeURIComponent(id));
    if (window.htmx) htmx.ajax("GET", url, { target: "#node-panel", swap: "innerHTML" });
  }

  function focusOn(id) {
    state.focus = id;
    load();
  }

  cy.on("tap", "node", (e) => { highlight(e.target); openPanel(e.target.id()); });
  cy.on("dbltap", "node", (e) => focusOn(e.target.id()));
  cy.on("tap", (e) => { if (e.target === cy) clearHighlight(); });
  cy.on("mouseover", "node", () => { cy.container().style.cursor = "pointer"; });
  cy.on("mouseout", "node", () => { cy.container().style.cursor = ""; });

  form.addEventListener("input", (e) => {
    syncOutputs();
    if (e.target.type === "range") return; // on attend le relâchement
    if (e.target.name === "types") syncPreset();
    if (e.target.id !== "f-layout") load();
  });
  form.addEventListener("change", (e) => {
    if (e.target.type === "range") load();
  });
  layoutSelect.addEventListener("change", runLayout);

  document.querySelectorAll("[data-preset]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const types = btn.dataset.types.split(",");
      form.querySelectorAll("input[name='types']").forEach((cb) => { cb.checked = types.includes(cb.value); });
      syncPreset();
      load();
    });
  });

  unfocusBtn.addEventListener("click", () => { state.focus = ""; load(); });
  document.getElementById("btn-fit").addEventListener("click", () => cy.animate({ fit: { padding: 40 } }, { duration: reduceMotion ? 0 : 300 }));
  document.getElementById("btn-png").addEventListener("click", () => {
    const a = document.createElement("a");
    a.href = cy.png({ full: true, scale: 2, bg: "#ECECE6" });
    a.download = "terroirs-graphe.png";
    a.click();
  });

  // Délégation : boutons du panneau
  document.getElementById("node-panel").addEventListener("click", (e) => {
    const t = e.target.closest("button");
    if (!t) return;
    if (t.dataset.focus) focusOn(t.dataset.focus);
    else if (t.dataset.select) selectOrFocus(t.dataset.select);
    else if (t.dataset.setPath) setPath(t.dataset.setPath, t.dataset.id, t.dataset.label);
  });

  function selectOrFocus(id) {
    const n = cy.getElementById(id);
    if (n.nonempty()) {
      cy.$(":selected").unselect();
      n.select();
      highlight(n);
      cy.animate({ center: { eles: n }, zoom: Math.max(cy.zoom(), 1) }, { duration: reduceMotion ? 0 : 300 });
      openPanel(id);
    } else {
      ensureType(id.split(":")[0]);
      focusOn(id);
    }
  }

  function ensureType(type) {
    const cb = form.querySelector(`input[name='types'][value='${type}']`);
    if (cb && !cb.checked) { cb.checked = true; syncPreset(); }
  }

  // Recherche
  const searchInput = document.getElementById("node-search");
  const search = Combo.attach(searchInput, {
    source: async (q) => (await Combo.getJSON(`${SEARCH}?q=${encodeURIComponent(q)}`)).results
      .map((r) => ({ ...r, hint: r.type_label })),
    onSelect: (it) => { search.clear(); selectOrFocus(it.id); },
  });

  // ── Plus court chemin ───────────────────────────────────────────────────
  const pathResult = document.getElementById("path-result");
  let pathPicking = null;

  document.querySelectorAll("[data-path-slot]").forEach((btn) => {
    btn.addEventListener("click", () => {
      pathPicking = btn.dataset.pathSlot;
      document.querySelectorAll("[data-path-slot]").forEach((b) => b.classList.toggle("is-picking", b === btn));
      stats.textContent = "Cliquez sur un nœud du graphe, ou utilisez les boutons Départ et Arrivée de sa fiche.";
    });
  });
  cy.on("tap", "node", (e) => {
    if (!pathPicking) return;
    setPath(pathPicking, e.target.id(), e.target.data("label"));
    pathPicking = null;
    document.querySelectorAll("[data-path-slot]").forEach((b) => b.classList.remove("is-picking"));
  });

  function setPath(slot, id, label) {
    state.path[slot] = { id, label };
    const btn = document.querySelector(`[data-path-slot='${slot}']`);
    btn.querySelector("strong").textContent = label;
    if (state.path.a && state.path.b) fetchPath();
  }

  let currentPath = null;
  async function fetchPath() {
    const { a, b } = state.path;
    const data = await Combo.getJSON(`${PATH}?a=${encodeURIComponent(a.id)}&b=${encodeURIComponent(b.id)}`);
    currentPath = data.path;
    pathResult.hidden = false;
    pathResult.innerHTML = "";
    if (!data.path) {
      pathResult.innerHTML = `<li class="muted">${data.message}</li>`;
      return;
    }
    data.path.forEach((step) => {
      const li = document.createElement("li");
      if (step.edge) {
        const rel = document.createElement("span");
        rel.className = "path-rel";
        rel.textContent = step.edge.forward ? step.edge.label : `← ${step.edge.label}`;
        li.appendChild(rel);
      }
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = `tag tag--${step.node.type}`;
      btn.textContent = step.node.label;
      btn.addEventListener("click", () => selectOrFocus(step.node.id));
      li.appendChild(btn);
      pathResult.appendChild(li);
    });
    drawPath();
  }

  function drawPath() {
    cy.elements(".path").removeClass("path");
    cy.elements(".path-extra").remove();
    if (!currentPath) return;
    let prev = null;
    currentPath.forEach((step) => {
      let n = cy.getElementById(step.node.id);
      if (n.empty()) {
        n = cy.add({ group: "nodes", data: { id: step.node.id, label: step.node.label, type: step.node.type, degree: 1, hue: COLORS.aroma } });
        n.addClass("path-extra");
        if (prev) n.position({ x: prev.position("x") + 60, y: prev.position("y") + 40 });
      }
      n.addClass("path");
      if (prev) {
        let e = prev.edgesWith(n);
        if (e.empty()) {
          e = cy.add({ group: "edges", data: { id: `path-${prev.id()}-${n.id()}`, source: prev.id(), target: n.id(), kind: step.edge.kind } });
          e.addClass("path-extra");
        }
        e.addClass("path");
      }
      prev = n;
    });
    cy.elements().addClass("faded").removeClass("hl");
    cy.elements(".path").removeClass("faded");

    // Si le chemin sort de la vue courante, on l'aligne pour le rendre lisible.
    const pathNodes = cy.nodes(".path");
    if (cy.nodes(".path-extra").nonempty()) {
      const ext = cy.extent();
      const cx = (ext.x1 + ext.x2) / 2;
      const cy0 = (ext.y1 + ext.y2) / 2;
      const step = 110;
      currentPath.forEach((s, i) => {
        cy.getElementById(s.node.id).position({
          x: cx + (i - (currentPath.length - 1) / 2) * step,
          y: cy0 + (i % 2 ? 40 : -40),
        });
      });
    }
    cy.animate({ fit: { eles: pathNodes, padding: 80 } }, { duration: reduceMotion ? 0 : 400 });
  }

  // ── Démarrage ────────────────────────────────────────────────────────────
  applyParams(new URLSearchParams(location.search));
  if (state.focus) ensureType(state.focus.split(":")[0]);
  load();
})();
