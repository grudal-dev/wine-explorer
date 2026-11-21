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
      // ── Bouquet (vue d'un vin, ordinateur) : le verre en bas, les molécules montent en bulles ──
      { selector: "node.bq[type='profile']", style: { "shape": "rectangle", "width": 74, "height": 124,
        "background-opacity": 0, "border-width": 0, "background-image": (n) => glass(n.data("wine")),
        "background-fit": "contain", "background-clip": "none", "label": "data(label)", "text-valign": "bottom",
        "text-halign": "center", "text-margin-x": 0, "text-margin-y": 10, "font-family": "Fraunces, Georgia, serif",
        "font-size": 21, "font-weight": 600, "text-background-opacity": 0, "text-max-width": 260 }},
      { selector: "node.bq[type='molecule']", style: { "shape": "ellipse",
        "width": (n) => 58 + 14 * (n.data("strength") || 1), "height": (n) => 58 + 14 * (n.data("strength") || 1),
        "padding": "0px", "background-color": "data(hue)", "border-width": 7, "border-color": "data(hue)", "border-opacity": 0.2,
        "label": bubbleLabel, "color": "#fff", "font-family": "Fraunces, Georgia, serif", "font-style": "italic",
        "font-weight": 600, "font-size": (n) => ((n.data("strength") || 1) >= 3 ? 14.5 : (n.data("odor") || "").length > 10 ? 10.5 : 12), "text-valign": "center",
        "text-halign": "center", "text-margin-x": 0, "text-margin-y": 0, "text-wrap": "wrap",
        "text-max-width": (n) => 48 + 14 * (n.data("strength") || 1), "text-background-opacity": 0, "line-height": 1.15 }},
      { selector: "node.bq[type='molecule'][tier='family']", style: { "background-opacity": 0.75 }},
      { selector: "node.bq[type='molecule'][tier='universal'], node.bq[type='molecule'][?universal]", style: {
        "background-opacity": 0.42, "color": C.ink, "border-opacity": 0.1 }},
      { selector: "node.bq[type='source']", style: { "shape": "round-rectangle", "width": "label", "height": 26,
        "padding": "9px", "background-color": "#FFFFFF", "border-width": 1.3, "border-color": "data(hue)",
        "label": "data(label)", "font-size": 12.5, "color": C.ink2, "text-valign": "center", "text-halign": "center",
        "text-margin-x": 0, "text-background-opacity": 0 }},
      { selector: "edge.bq[kind='contains']", style: { "curve-style": "unbundled-bezier",
        "control-point-distances": (e) => [-(e.target().position("x") - e.source().position("x")) * 0.32],
        "control-point-weights": [0.55], "opacity": 0.75, "width": "mapData(strength, 1, 3, 2, 6)" }},
      { selector: "edge.bq[kind='found_in']", style: { "curve-style": "straight", "line-color": (e) => e.target().data("hue"),
        "opacity": 0.4, "width": 1.2 }},
      // Couronne d'une molécule : la molécule en grande bulle au centre, les vins en petits verres autour.
      { selector: "node.bq[type='molecule'][?root]", style: { "width": 132, "height": 132, "font-size": 16,
        "text-max-width": 116, "border-width": 10, "border-opacity": 0.22, "label": rootLabel }},
      { selector: "node.bq.ring[type='profile']", style: { "width": 20, "height": 34, "font-family": "Inter, system-ui, sans-serif",
        "font-size": 12, "font-weight": 500, "color": C.ink, "text-valign": "center", "text-halign": "center",
        "text-margin-x": "data(lx)", "text-margin-y": "data(ly)", "text-rotation": "data(rot)", "text-wrap": "none",
        "text-background-opacity": 0 }},
      { selector: "edge.bq.ring[kind='contains']", style: { "curve-style": "straight", "opacity": 0.45,
        "width": "mapData(strength, 1, 3, 1.2, 4)" }},
      { selector: "node.bq:selected", style: { "border-color": C.garnet, "border-opacity": 1, "border-width": 4 }},
      { selector: "node.bq.hl[type='molecule']", style: { "border-color": "data(hue)", "border-opacity": 0.35, "border-width": 9 }},
    ],
  });

  // Verre dessiné (couleur du vin) : nœud du vin dans le bouquet.
  const ROBE = { rouge: "#6E1A33", blanc: "#E2C766", rose: "#E89A8C" };
  function glass(wine) {
    const fill = ROBE[wine] || ROBE.rouge;
    return "data:image/svg+xml;utf8," + encodeURIComponent(
      "<svg xmlns='http://www.w3.org/2000/svg' viewBox='-50 -116 100 168'>"
      + "<path d='M-46 -112 H46 C46 -58 28 -26 0 -22 C-28 -26 -46 -58 -46 -112 Z' fill='#fff' stroke='#23262F' stroke-width='2.5'/>"
      + `<path d='M-43 -80 H43 C40 -50 24 -28 0 -25 C-24 -28 -40 -50 -43 -80 Z' fill='${fill}'/>`
      + "<path d='M0 -22 V40' stroke='#23262F' stroke-width='2.5'/>"
      + "<path d='M-30 46 Q0 34 30 46' fill='none' stroke='#23262F' stroke-width='2.5' stroke-linecap='round'/></svg>");
  }
  // Dans une bulle : l'odeur d'abord (« poivre noir »), le nom de la molécule dessous, abrégé s'il est long.
  function bubbleLabel(n) {
    const name = n.data("label") || "";
    const room = 6 + 2 * (n.data("strength") || 1);
    const short = name.length > room ? `${name.slice(0, room - 1)}…` : name;
    const odor = n.data("odor") || "";
    return odor && odor.toLowerCase() !== name.toLowerCase() ? `${odor}\n${short}` : short;
  }
  function rootLabel(n) {
    const odor = n.data("odor") || "";
    const name = n.data("label") || "";
    return odor && odor.toLowerCase() !== name.toLowerCase() ? `${odor}\n${name}` : name;
  }
  const wide = () => cy.width() >= 640;
  const bouquetMode = () => state.start.startsWith("profile:") && wide();
  const ringMode = () => state.start.startsWith("molecule:") && wide();
  function layout() {
    if (bouquetMode()) layoutBouquet();
    else if (ringMode()) layoutRing();
    else layoutColumns();
  }

  // ── Couronne : une molécule au centre, ses vins en verres tout autour (par couleur), sa nature au-dessus ──
  const measureCtx = document.createElement("canvas").getContext("2d");
  function layoutRing() {
    const canvas = cy.container().parentElement;
    canvas.classList.add("is-bouquet");
    const wines = cy.nodes("[type='profile']");
    // Le cadre se règle sur la largeur : un cercle de rayon R, plus la place des noms et de la nature.
    const R0 = Math.max(170, Math.min(cy.width() / 2 - 150, 330));
    // Au-dessus : la nature (0,86 R) ; en dessous : le cercle et les noms qui en partent (≈ 190 px).
    const want = `${Math.round(1.86 * R0 + 260)}px`;
    if (canvas.style.minHeight !== want) { canvas.style.minHeight = want; cy.resize(); }
    cy.elements().addClass("bq ring");
    cy.nodes().removeClass("compact");
    const W = cy.width(), H = cy.height();
    const rad = (d) => (d * Math.PI) / 180;
    const cx = W / 2;
    const positions = {};

    // Les vins : rouges, rosés puis blancs, du lien le plus sûr au plus faible, sur l'arc du bas
    // (de 62° à 298°, le haut est laissé à la nature). Les noms rayonnent vers l'extérieur.
    const order = { rouge: 0, rose: 1, blanc: 2 };
    const list = wines.toArray().sort((a, b) => (order[a.data("wine")] ?? 3) - (order[b.data("wine")] ?? 3)
      || (b.connectedEdges()[0]?.data("strength") || 0) - (a.connectedEdges()[0]?.data("strength") || 0)
      || (a.data("label") || "").localeCompare(b.data("label") || ""));
    const R = R0;
    const cyy = Math.max(0.86 * R + 50, H - R - 200);
    cy.nodes("[type='molecule']").forEach((m) => { positions[m.id()] = { x: cx, y: cyy }; });
    const n = list.length;
    const from = 62, to = 298;
    measureCtx.font = "500 12px Inter, system-ui, sans-serif";
    list.forEach((w, k) => {
      const a = n > 1 ? from + ((to - from) * k) / (n - 1) : 180;
      const ux = Math.sin(rad(a)), uy = -Math.cos(rad(a));
      positions[w.id()] = { x: cx + R * ux, y: cyy + R * uy };
      const half = measureCtx.measureText(w.data("label") || "").width / 2;
      const off = half + 18;
      // Lecture de gauche à droite : à gauche du cercle, on retourne le texte.
      let rot = Math.atan2(uy, ux);
      if (ux < 0) rot += Math.PI;
      w.data({ lx: ux * off, ly: uy * off, rot });
    });
    // La nature : une couronne d'étiquettes dans l'éventail du haut.
    const srcs = cy.nodes("[type='source']").toArray();
    const ns = srcs.length;
    // Deux rangées en quinconce au-dessus de la bulle, écartées pour que les étiquettes ne se touchent pas.
    const rows = [[], []];
    srcs.forEach((s, k) => rows[k % 2].push(s));
    measureCtx.font = "400 12.5px Inter, system-ui, sans-serif";
    rows.forEach((row, r) => {
      const y = cyy - R * (r ? 0.62 : 0.86);
      const widths = row.map((s) => measureCtx.measureText(s.data("label") || "").width + 30);
      const total = widths.reduce((a, b) => a + b, 0) + 12 * Math.max(0, row.length - 1);
      let x = cx - total / 2;
      row.forEach((s, k) => { positions[s.id()] = { x: x + widths[k] / 2, y }; x += widths[k] + 12; });
    });
    run(positions, false);
  }

  // ── Bouquet : le vin en bas, ses molécules en éventail au-dessus, la nature en couronne ──
  function layoutBouquet() {
    const canvas = cy.container().parentElement;
    canvas.classList.add("is-bouquet");
    if (canvas.style.minHeight !== "820px") { canvas.style.minHeight = "820px"; cy.resize(); }
    cy.elements().addClass("bq").removeClass("ring");
    cy.nodes().removeClass("compact");
    const W = cy.width(), H = cy.height();
    const rad = (d) => (d * Math.PI) / 180;
    const ox = W / 2, oy = H - 230;           // foyer de l'éventail, au-dessus du verre
    const positions = {};
    cy.nodes("[type='profile']").forEach((n) => { positions[n.id()] = { x: ox, y: H - 150 }; });
    // Molécules : les plus sûres au centre, en quinconce sur deux ou trois anneaux.
    const mols = cy.nodes("[type='molecule']").sort((a, b) => (b.data("strength") || 0) - (a.data("strength") || 0)
      || (a.data("universal") ? 1 : 0) - (b.data("universal") ? 1 : 0));
    const n = mols.length;
    const slots = [...Array(n).keys()].sort((a, b) => Math.abs(a - (n - 1) / 2) - Math.abs(b - (n - 1) / 2));
    const rings = n > 9 ? [1, 0.78, 0.56] : [1, 0.7];
    const rx = Math.min(W * 0.4, 360), ry = Math.min((oy - 60) * 0.68, 390);
    const spanM = Math.min(140, 40 + n * 14);
    const angle = {};
    mols.forEach((m, k) => {
      const slot = slots[k];
      const a = n > 1 ? -spanM / 2 + (spanM * slot) / (n - 1) : 0;
      const ring = rings[slot % rings.length];
      angle[m.id()] = a;
      positions[m.id()] = { x: ox + rx * ring * Math.sin(rad(a)), y: oy - ry * ring * Math.cos(rad(a)) };
    });
    // Les bulles ne se touchent pas : on les écarte deux à deux (au-dessus du verre, dans le cadre).
    const size = (m) => (58 + 14 * (m.data("strength") || 1)) / 2;
    const ms = mols.toArray();
    for (let it = 0; it < 60; it++) {
      let moved = false;
      for (let i = 0; i < ms.length; i++) {
        for (let j = i + 1; j < ms.length; j++) {
          const p = positions[ms[i].id()], q = positions[ms[j].id()];
          const need = size(ms[i]) + size(ms[j]) + 30; // halo de 7 px de chaque bulle compris
          const dx = q.x - p.x, dy = q.y - p.y, d = Math.hypot(dx, dy) || 0.01;
          if (d >= need) continue;
          const push = (need - d) / 2, ux = dx / d, uy = dy / d;
          p.x -= ux * push; p.y -= uy * push; q.x += ux * push; q.y += uy * push;
          moved = true;
        }
      }
      ms.forEach((m) => {
        const p = positions[m.id()], r = size(m);
        p.x = Math.min(W - r - 10, Math.max(r + 10, p.x));
        p.y = Math.min(oy - r + 10, Math.max(r + 70, p.y));
      });
      if (!moved) break;
    }
    // Éléments naturels : une couronne au-dessus, dans l'ordre des molécules qu'ils prolongent.
    const srcs = cy.nodes("[type='source']").toArray().map((s) => {
      const as = s.incomers("node").map((m) => angle[m.id()]).filter((v) => v !== undefined);
      return { s, a: as.length ? as.reduce((x, y) => x + y, 0) / as.length : 0 };
    }).sort((p, q) => p.a - q.a);
    const ns = srcs.length;
    const sx = Math.min(W / 2 - 70, rx * 1.5), sy = oy - 34;
    const spanS = Math.min(170, 60 + ns * 9);
    const bubbles = mols.map((m) => ({ ...positions[m.id()], r: (58 + 14 * (m.data("strength") || 1)) / 2 + 8 }));
    const placed = [];
    srcs.forEach(({ s }, k) => {
      const a = ns > 1 ? -spanS / 2 + (spanS * k) / (ns - 1) : 0;
      let r = k % 2 ? 0.88 : 1;
      const half = ((s.data("label") || "").length * 7 + 22) / 2;
      const at = () => ({ x: Math.min(W - half - 8, Math.max(half + 8, ox + sx * r * Math.sin(rad(a)))),
        y: Math.max(26, oy - sy * r * Math.cos(rad(a))) });
      // Une étiquette ne doit couvrir ni une bulle ni une autre étiquette : on la pousse vers l'extérieur.
      const hits = (p) => bubbles.some((b) => Math.abs(p.x - b.x) < half + b.r && Math.abs(p.y - b.y) < 14 + b.r)
        || placed.some((q) => Math.abs(p.x - q.x) < half + q.half + 6 && Math.abs(p.y - q.y) < 32);
      let p = at();
      for (let i = 0; i < 24 && hits(p); i++) { r += 0.04; p = at(); }
      placed.push({ ...p, half });
      positions[s.id()] = p;
    });
    run(positions, false);
  }

  // ── Disposition en colonnes ─────────────────────────────────────────────
  // Les colonnes occupent la largeur du cadre ; l'espacement vertical s'adapte au nombre de
  // nœuds pour garder des libellés lisibles (zoom 1) tant que tout tient à l'écran.
  let colX = [0, 420, 840];
  function layoutColumns() {
    const W = cy.width();
    // Ordinateur : le cadre grandit avec le nombre de nœuds (la page défile) pour que le graphe reste
    // au zoom 1. Téléphone : hauteur fixe, comme avant.
    const canvas = cy.container().parentElement;
    canvas.classList.remove("is-bouquet");
    cy.elements().removeClass("bq ring");
    if (W >= 640) {
      const counts = [0, 0, 0];
      cy.nodes().forEach((n) => counts[n.data("layer")]++);
      const need = Math.min(64 + 36 + Math.max((counts[1] - 1) * 70, (Math.max(counts[0], counts[2]) - 1) * 30, 0) + 40, 1600);
      const px = `${Math.round(need)}px`;
      if (canvas.style.minHeight !== px) { canvas.style.minHeight = px; cy.resize(); }
    } else if (canvas.style.minHeight) {
      canvas.style.minHeight = ""; cy.resize();
    }
    const H = cy.height();
    // Téléphone : même dessin qu'avant (hexagone, nom dessous), les étiquettes pleines y seraient trop larges.
    cy.nodes().toggleClass("compact", W < 640);
    // Téléphone (< 640 px) : dessin inchangé, sur 760 px puis recadré. Au-delà, les colonnes suivent la
    // largeur réelle du cadre, pour rester au zoom 1 (lisible) sur les écrans moyens.
    const compact = W < 640;
    const span = compact ? Math.max(W, 760) : W;
    colX = compact
      ? [Math.max(span * 0.2, 190), span * 0.5, Math.min(span * 0.8, span - 190)]
      : [Math.max(span * 0.2, 165), span * 0.52, Math.min(span * 0.8, span - 150)];
    const layers = [[], [], []];
    cy.nodes().forEach((n) => layers[n.data("layer")].push(n));
    const top = 64;
    const usable = Math.max(H - top - 36, 200);
    const positions = {};
    let overflow = compact;
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
    if (cy.container().parentElement.classList.contains("is-bouquet")) { columns.forEach((el) => { el.hidden = true; }); return; }
    const pan = cy.pan();
    const z = cy.zoom();
    const present = new Set(cy.nodes().map((n) => n.data("layer")));
    // Les libellés des vins partent à gauche du nœud, ceux de la nature à droite : on aligne
    // les titres de la même façon, ce qui les écarte quand le graphe est dézoomé.
    const anchor = ["-100%", "-50%", "0%"];
    const nudge = [12, 0, -8];
    columns.forEach((el) => {
      const i = +el.dataset.col;
      el.classList.remove("is-tight");
      el.hidden = !present.has(i);
      el.style.transform = `translateX(${anchor[i]})`;
      el.style.left = `${(colX[i] + nudge[i]) * z + pan.x}px`;
    });
    // Si les titres se touchent encore, on les réduit, puis on masque celui du milieu.
    const visible = [...columns].filter((el) => !el.hidden).sort((a, b) => a.dataset.col - b.dataset.col);
    const overlaps = () => visible.some((el, k) => k > 0
      && visible[k - 1].getBoundingClientRect().right + 8 > el.getBoundingClientRect().left);
    if (overlaps()) {
      visible.forEach((el) => el.classList.add("is-tight"));
      if (overlaps() && visible.length === 3) visible[1].hidden = true;
    }
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
      const more = kind === "molecule" && wide() ? "&vins=32" : "";
      data = await Combo.getJSON(`${API}?kind=${kind}&slug=${encodeURIComponent(slug)}${query()}${more}`);
    } catch (err) {
      stats.textContent = _("Impossible de charger ce graphe.");
      return;
    }
    if (mine !== seq) return;
    state.start = id;
    cy.elements().remove();
    cy.add(data.elements);
    layout();
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
        + (s.truncated ? " " + _("(et %s autres, tous listés dans la fiche)").replace("%s", s.truncated) : ""));
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

  document.getElementById("mol-fit").addEventListener("click", () => layout());
  window.addEventListener("resize", () => { clearTimeout(window.__molResize); window.__molResize = setTimeout(layout, 200); });
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

  // Légende : ouverte seulement sur un écran large ET haut ; ailleurs (téléphone, portable avec mise à
  // l'échelle de Windows) elle prendrait la moitié de la hauteur du graphe.
  const legend = document.getElementById("mol-legend");
  if (legend && window.matchMedia("(min-width: 721px) and (min-height: 900px)").matches) legend.open = true;
  // La légende change la hauteur du graphe : on le remesure avant de placer les nœuds.
  cy.resize();
  if (legend) legend.addEventListener("toggle", () => { cy.resize(); if (state.start) layout(); });

  // Le cadre change de hauteur quand la ligne de résumé ou la légende passent sur plusieurs lignes :
  // on remesure, sinon le bas du graphe est coupé.
  if (window.ResizeObserver) {
    let lastH = 0;
    new ResizeObserver(() => {
      const h = cy.container().clientHeight;
      if (Math.abs(h - lastH) < 2) return;
      lastH = h;
      clearTimeout(window.__molResize);
      window.__molResize = setTimeout(() => { cy.resize(); if (state.start) layout(); }, 120);
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
