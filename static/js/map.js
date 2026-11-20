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

  const WINE = { rouge: "#6B1730", blanc: "#D9C36A", rose: "#F4AFA6" };
  // Nuances (voir api_map) : blancs du paille clair (sec, 0) à l'ambre (liquoreux, 5) ; rouges du rubis
  // clair (tanins souples) au grenat d'encre (tanins serrés) ; rosés saumon clair. Les trois familles
  // ne se recouvrent pas : le rubis le plus clair reste plus sombre et plus froid que le rosé.
  const WHITES = ["#F1E9B6", "#E8D785", "#DEC25A", "#D3A73C", "#C68A28", "#B06C1B"];
  const REDS = ["#C2475F", "#C2475F", "#A53150", "#842041", "#621332", "#3F0A22"];
  const BORDER = { blanc: "#8C7424", rose: "#B0574C", rouge: "#23262F" };
  function wineShade(n) {
    if (n.wine === "blanc") return WHITES[Math.max(0, Math.min(5, n.sweet ?? 0))];
    if (n.wine === "rouge") return REDS[Math.max(0, Math.min(5, n.tannin ?? 3))];
    return WINE.rose;
  }
  const TYPE = { grape: "#56662D", aroma: "#B07D22", appellation: "#7A1F3D", region: "#3B5878", molecule: "#2E6E6A" };
  // Palette qualitative pour les régions (12 teintes distinctes sur fond clair).
  const PALETTE = ["#7A1F3D", "#3B5878", "#56662D", "#B07D22", "#2E6E6A", "#A4502A", "#6B4A8A", "#C2334D",
    "#4F7CAC", "#8A8D2F", "#B57BB0", "#5C5145", "#1F7A5A", "#C8782A"];
  const regionColor = {};
  let regionNames = {};

  // Tailles constantes à l'écran : un point fait toujours ~16 px et un nom ~12 px, quel que soit le zoom.
  // Le cadrage d'ensemble reste lisible, et zoomer écarte les points au lieu de les grossir.
  let K = 1;
  // Téléphone : points et écarts plus petits (138 points de 16 px ne tiennent pas en 390 px sans se
  // toucher) ; les noms gardent leur taille.
  const SMALL = document.getElementById("map-cy").clientWidth < 640;
  const SZ = SMALL ? 0.68 : 1;
  const GAP = SMALL ? 13.5 : 20;
  const px = (v) => () => v * K * SZ;   // tailles des points et des traits
  const pt = (v) => () => v * K;        // tailles des textes

  const cy = cytoscape({
    container: document.getElementById("map-cy"),
    minZoom: 0.2, maxZoom: 8, boxSelectionEnabled: false, autoungrabify: true,
    style: [
      { selector: "node", style: {
        "label": "data(label)", "font-family": "Inter, system-ui, sans-serif", "font-size": pt(12), "font-weight": 500,
        "color": "#23262F", "text-valign": "bottom", "text-margin-y": pt(4),
        "text-background-color": "#F8F8F4", "text-background-opacity": 0.88, "text-background-padding": pt(2),
        "text-background-shape": "roundrectangle",
        "width": px(12), "height": px(12), "background-color": "data(color)", "border-width": px(1), "border-color": "#23262F",
        "transition-property": "opacity, width, height, border-width", "transition-duration": "150ms",
      }},
      { selector: "node[type='profile']", style: { "width": px(16), "height": px(16), "border-width": px(1.5) }},
      { selector: "node[type='profile'][wine='blanc']", style: { "border-color": BORDER.blanc }},
      { selector: "node[type='profile'][wine='rose']", style: { "border-color": BORDER.rose, "border-width": px(2) }},
      { selector: "node[type='grape']", style: { "shape": "diamond", "font-style": "italic" }},
      { selector: "node[type='aroma']", style: { "shape": "ellipse", "width": px(10), "height": px(10), "border-width": 0, "font-style": "italic" }},
      { selector: "node[type='appellation']", style: { "shape": "round-rectangle", "width": px(10), "height": px(10) }},
      { selector: "node[type='region']", style: { "shape": "round-rectangle", "width": px(20), "height": px(13), "font-weight": 700, "font-size": pt(13) }},
      { selector: "node[type='molecule']", style: { "shape": "hexagon" }},
      // Position du nom choisie par placeLabels : dessous (défaut), dessus, à droite, à gauche.
      { selector: "node.lab-t", style: { "text-valign": "top", "text-margin-y": pt(-4) }},
      { selector: "node.lab-r", style: { "text-valign": "center", "text-halign": "right", "text-margin-x": pt(5), "text-margin-y": 0 }},
      { selector: "node.lab-l", style: { "text-valign": "center", "text-halign": "left", "text-margin-x": pt(-5), "text-margin-y": 0 }},
      // Libellé masqué quand il chevaucherait un voisin (voir placeLabels) ; il revient au survol et au zoom.
      { selector: "node.hover", style: { "text-opacity": 1, "text-background-opacity": 0.95, "z-index": 20,
        "width": px(22), "height": px(22) }},
      { selector: ".dim", style: { "opacity": 0.15, "text-opacity": 0 }},
      { selector: ".off", style: { "display": "none" }},
      { selector: "node.near", style: { "text-opacity": 1, "text-background-opacity": 0.95, "font-weight": 600, "z-index": 9 }},
      // Après .near : un voisin sans place pour son nom reste sans nom (il est listé dans le panneau).
      { selector: "node.quiet", style: { "text-opacity": 0, "text-background-opacity": 0 }},
      { selector: "node:selected", style: { "border-color": "#7A1F3D", "text-opacity": 1,
        "text-background-opacity": 0.95, "font-weight": 700, "font-size": pt(13.5), "z-index": 10, "overlay-opacity": 0,
        "width": px(26), "height": px(26), "border-width": px(4) }},
      { selector: "edge", style: { "width": (e) => (1.5 + 4.5 * Math.max(0, (e.data("similarity") - 0.5) / 0.5)) * K, "line-color": "#7A1F3D",
        "opacity": 0.55, "curve-style": "straight" }},
    ],
  });

  // ── Libellés sans chevauchement ──────────────────────────────────────
  // À chaque zoom, on garde les libellés qui tiennent sans toucher un autre libellé ni un point, en
  // commençant par les vins les plus isolés : à l'arrivée, la carte se lit sans rien faire.
  const measure = document.createElement("canvas").getContext("2d");
  let labelTimer = 0;
  function placeLabels() {
    const z = cy.zoom();
    const boxes = [];
    const W = cy.width(), H = cy.height();
    const hits = (b) => b[0] < 2 || b[1] < 2 || b[2] > W - 2 || b[3] > H - 2
      || boxes.some((o) => b[0] < o[2] && b[2] > o[0] && b[1] < o[3] && b[3] > o[1]);
    // Quand un vin est choisi, les points estompés ne réservent pas de place pour leur nom.
    const nodes = cy.nodes().not(".off");
    const named = nodes.not(".dim");
    nodes.difference(named).addClass("quiet");
    named.forEach((n) => {
      const p = n.renderedPosition();
      const r = (n.width() * z) / 2 + 1;
      boxes.push([p.x - r, p.y - r, p.x + r, p.y + r]);
    });
    // Le vin choisi (toujours nommé) et ses voisins d'abord, puis les plus isolés.
    const prio = (n) => (n.selected() ? 2 : n.hasClass("near") ? 1 : 0);
    const ranked = named.sort((a, b) => prio(b) - prio(a) || (b.data("iso") || 0) - (a.data("iso") || 0));
    cy.batch(() => {
      ranked.forEach((n) => {
        n.removeClass("lab-t lab-r lab-l");
        const fs = n.data("type") === "region" ? 13 : 12;
        measure.font = `${n.selected() ? 700 : n.hasClass("near") ? 600 : 500} ${n.selected() ? 13.5 : fs}px Inter, system-ui, sans-serif`;
        const w = measure.measureText(n.data("label") || "").width + 6;
        const h = fs * 1.35 + 4;
        const p = n.renderedPosition();
        const r = (n.width() * z) / 2;
        const spots = [
          ["", [p.x - w / 2, p.y + r + 3, p.x + w / 2, p.y + r + 3 + h]],
          ["lab-t", [p.x - w / 2, p.y - r - 3 - h, p.x + w / 2, p.y - r - 3]],
          ["lab-r", [p.x + r + 4, p.y - h / 2, p.x + r + 4 + w, p.y + h / 2]],
          ["lab-l", [p.x - r - 4 - w, p.y - h / 2, p.x - r - 4, p.y + h / 2]],
        ];
        const spot = spots.find(([, b]) => !hits(b)) || (n.selected() ? spots[0] : null);
        if (spot) { boxes.push(spot[1]); if (spot[0]) n.addClass(spot[0]); }
        n.toggleClass("quiet", !spot);
      });
    });
  }
  const scheduleLabels = () => { clearTimeout(labelTimer); labelTimer = setTimeout(placeLabels, 60); };
  let styleFrame = 0;
  cy.on("zoom", () => {
    K = 1 / cy.zoom();
    if (!styleFrame) styleFrame = requestAnimationFrame(() => { styleFrame = 0; cy.style().update(); });
  });
  cy.on("zoom pan", scheduleLabels);

  // Isolement de chaque point (distance au plus proche voisin) : les plus isolés gardent leur nom d'abord.
  function computeIsolation() {
    const nodes = cy.nodes().not(".off").toArray();
    nodes.forEach((a) => {
      const pa = a.position();
      let best = Infinity;
      nodes.forEach((b) => {
        if (a === b) return;
        const pb = b.position();
        const d = (pa.x - pb.x) ** 2 + (pa.y - pb.y) ** 2;
        if (d < best) best = d;
      });
      a.data("iso", best);
    });
  }

  // t-SNE tasse les vins d'une même famille les uns sur les autres : on écarte les points qui se
  // touchent (distance `gap`), mais chaque point reste attiré par sa place d'origine (ressort) :
  // les petits groupes restent des groupes, séparés par du vide.
  function spread(gap) {
    const nodes = cy.nodes("[type='profile']").toArray();
    const home = nodes.map((n) => ({ ...n.position() }));
    const pos = home.map((p) => ({ ...p }));
    for (let it = 0; it < 120; it++) {
      for (let i = 0; i < pos.length; i++) {
        for (let j = i + 1; j < pos.length; j++) {
          const dx = pos[j].x - pos[i].x, dy = pos[j].y - pos[i].y;
          const d = Math.hypot(dx, dy) || 0.01;
          if (d >= gap) continue;
          const push = (gap - d) / 2;
          const ux = dx / d, uy = dy / d;
          pos[i].x -= ux * push; pos[i].y -= uy * push;
          pos[j].x += ux * push; pos[j].y += uy * push;
        }
      }
      // Le ressort faiblit au fil des passes : les dernières ne font plus qu'écarter, sans chevauchement.
      const k = 0.06 * Math.max(0, 1 - it / 80);
      for (let i = 0; k && i < pos.length; i++) {
        pos[i].x += (home[i].x - pos[i].x) * k;
        pos[i].y += (home[i].y - pos[i].y) * k;
      }
    }
    cy.batch(() => nodes.forEach((n, k) => n.position(pos[k])));
  }

  // Écarter fait grandir la carte, donc recadrer la dézoome et resserre les points à l'écran : on
  // répète jusqu'à ce que l'écart à l'écran (GAP) tienne.
  function settle() {
    for (let i = 0; i < 5; i++) {
      const z = cy.zoom();
      spread(GAP / z);
      fitAll();
      if (cy.zoom() > z * 0.97) break;
    }
    computeIsolation();
    placeLabels();
  }

  function fitAll(animate = false) {
    cy.resize();
    const eles = cy.nodes().not(".off");
    if (animate && !reduceMotion) cy.animate({ fit: { eles, padding: 40 } }, { duration: 300, complete: placeLabels });
    else { cy.fit(eles, 40); K = 1 / cy.zoom(); cy.style().update(); placeLabels(); }
  }

  function nodeColor(n) {
    if (n.type !== "profile") return n.hue || TYPE[n.type] || "#23262F";
    if (form.color.value === "region") return regionColor[n.root] || "#8A8D94";
    return wineShade(n);
  }

  function drawLegend() {
    legend.innerHTML = "";
    legend.classList.toggle("is-scales", form.color.value !== "region");
    if (form.color.value === "region") {
      Object.keys(regionColor).forEach((slug) => {
        const li = document.createElement("li");
        const dot = document.createElement("i");
        dot.style.background = regionColor[slug];
        li.append(dot, document.createTextNode(regionNames[slug] || slug));
        legend.appendChild(li);
      });
      return;
    }
    // Couleur du vin : une échelle par famille.
    const scale = (title, colors, from, to, border) => {
      const li = document.createElement("li");
      li.className = "map-legend__scale";
      const strong = document.createElement("strong");
      strong.textContent = title;
      const ramp = document.createElement("span");
      ramp.className = "map-legend__ramp";
      colors.forEach((c) => {
        const i = document.createElement("i");
        i.style.background = c;
        i.style.borderColor = border;
        ramp.appendChild(i);
      });
      const ends = document.createElement("span");
      ends.className = "map-legend__ends";
      ends.textContent = `${from} → ${to}`;
      li.append(strong, ramp, ends);
      legend.appendChild(li);
    };
    scale(_("Blancs"), WHITES, _("sec"), _("liquoreux"), BORDER.blanc);
    scale(_("Rouges"), REDS.slice(1), _("tanins souples"), _("serrés"), BORDER.rouge);
    scale(_("Rosés"), [WINE.rose], "", "", BORDER.rose);
    legend.lastChild.querySelector(".map-legend__ends").remove();
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
    computeIsolation();
    scheduleLabels();
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
      // On cadre le voisinage ; points et noms gardent leur taille à l'écran, donc zoomer les écarte.
      cy.fit(group, 90);
      if (!reduceMotion) {
        node.animate({ style: { width: 42 * K * SZ, height: 42 * K * SZ } }, { duration: 260 })
          .animate({ style: { width: 26 * K * SZ, height: 26 * K * SZ } }, { duration: 260, complete: () => { node.removeStyle("width height"); placeLabels(); } });
      }
    }
    placeLabels();
  }

  cy.on("tap", "node", (e) => select(e.target.id()));
  cy.on("tap", (e) => { if (e.target === cy) { clearSelection(); cy.$(":selected").unselect(); placeLabels(); } });
  cy.on("mouseover", "node", (e) => { cy.container().style.cursor = "pointer"; e.target.addClass("hover"); });
  cy.on("mouseout", "node", (e) => { cy.container().style.cursor = ""; e.target.removeClass("hover"); });

  form.addEventListener("change", () => { clearSelection(); applyFilters(); fitAll(true); });
  document.getElementById("map-fit").addEventListener("click", () => fitAll(true));

  // ── Plein écran ─────────────────────────────────────────────────────────
  // API Fullscreen sur toute la carte (barre, carte, fiche) ; sinon (Safari sur iPhone), la carte
  // occupe toute la fenêtre par une classe. Échap ou le bouton en sortent ; on recadre à chaque bascule.
  const fsBtn = document.getElementById("map-fullscreen");
  const fsLabel = fsBtn.querySelector("span");
  const nativeFs = !!(root.requestFullscreen || root.webkitRequestFullscreen);
  const isFull = () => !!(document.fullscreenElement || document.webkitFullscreenElement) || root.classList.contains("is-fullscreen");
  function syncFs() {
    const on = isFull();
    root.classList.toggle("is-full", on);
    fsBtn.setAttribute("aria-pressed", on ? "true" : "false");
    fsLabel.textContent = on ? fsBtn.dataset.on : fsBtn.dataset.off;
    fsBtn.title = fsLabel.textContent;
    document.body.classList.toggle("map-is-full", on);
    requestAnimationFrame(() => { cy.resize(); fitAll(); });
  }
  function toggleFs() {
    if (isFull()) {
      if (document.fullscreenElement) document.exitFullscreen();
      else if (document.webkitFullscreenElement) document.webkitExitFullscreen();
      else { root.classList.remove("is-fullscreen"); syncFs(); }
      return;
    }
    if (nativeFs) {
      const req = root.requestFullscreen || root.webkitRequestFullscreen;
      Promise.resolve(req.call(root)).catch(() => { root.classList.add("is-fullscreen"); syncFs(); });
    } else {
      root.classList.add("is-fullscreen");
      syncFs();
    }
  }
  fsBtn.addEventListener("click", toggleFs);
  document.addEventListener("fullscreenchange", syncFs);
  document.addEventListener("webkitfullscreenchange", syncFs);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && root.classList.contains("is-fullscreen")) { root.classList.remove("is-fullscreen"); syncFs(); }
    if ((e.key === "f" || e.key === "F") && !e.ctrlKey && !e.metaKey && !e.altKey
        && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) toggleFs();
  });
  document.getElementById("map-png").addEventListener("click", () => {
    const a = document.createElement("a");
    a.href = cy.png({ full: true, scale: 2, bg: "#F8F8F4" });
    a.download = "wine-explorer-carte-des-gouts.png";
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
    // Échelle calée sur le cadre : au cadrage, le zoom reste proche de 1 et les points comme les noms
    // gardent leur taille réelle (avant : dessin sur 2 800 px réduit au quart, noms invisibles).
    cy.resize();
    const S = Math.max(300, Math.min(cy.width(), cy.height()) * 0.5);
    cy.add(data.nodes.map((n) => ({
      group: "nodes", data: { ...n, color: "#23262F" }, position: { x: n.x * S, y: n.y * S },
    })));
    applyFilters();
    fitAll();
    settle();
    if (root.dataset.focus) select(root.dataset.focus, { center: true });
    // Le cadre peut encore changer de taille (polices, barre de défilement) : on recadre tant que le
    // visiteur n'a pas touché à la carte.
    let touched = false;
    cy.one("tapstart scrollzoom", () => { touched = true; });
    if (window.ResizeObserver) {
      let t = 0;
      new ResizeObserver(() => {
        clearTimeout(t);
        t = setTimeout(() => {
          if (touched || root.dataset.focus) { cy.resize(); placeLabels(); return; }
          fitAll(); settle();
        }, 120);
      }).observe(cy.container());
    }
  }

  start();
})();
