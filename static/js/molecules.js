/* Graphe moléculaire : vin → molécules → arômes du vin ; molécule ou élément naturel → leurs liens. */
(function () {
  "use strict";

  const root = document.getElementById("mol-explorer");
  if (!root || !window.cytoscape) return;

  const API = root.dataset.api;
  const SEARCH = root.dataset.search;
  const PANEL = root.dataset.panel; // .../fiche/X/
  const PRINT = root.dataset.print; // .../imprimer/X/
  const RANDOM = (root.dataset.random || "").split(",").filter(Boolean);
  const stats = document.getElementById("mol-stats");
  const trailEl = document.getElementById("mol-trail");
  const commonBox = document.getElementById("mol-common");
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
    const odor = n.data("note") || n.data("odor");
    return odor && odor.toLowerCase() !== n.data("label").toLowerCase() ? `${n.data("label")}\n${odor}` : n.data("label");
  }

  const measureCtx = document.createElement("canvas").getContext("2d");
  const LINE = 1.15;   // interligne des bulles, partagé par le style et la mesure
  const state = { start: "", trail: [], common: false, wikidata: true, age: null, everything: false };
  const query = () => `${state.common ? "&commun=1" : ""}${state.age ? `&age=${state.age}` : ""}${state.everything ? "&tout=1" : ""}${state.wikidata ? "" : "&wikidata=0"}`;

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
      { selector: "node[type='molecule'][tier='universal'], node[type='molecule'][?universal]", style: {
        "background-color": "#D3E2E0", "color": "#27514E", "font-weight": 400 }},
      { selector: "node[type='source']", style: { "shape": "ellipse", "width": 14, "height": 14,
        "background-color": "data(hue)" }},
      { selector: "node[type='aroma']", style: { "shape": "ellipse", "width": 14, "height": 14,
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
      { selector: "edge[kind='found_in']", style: { "line-color": "#B9CCCA", "width": "mapData(strength, 1, 3, 1.2, 3.6)" }},
      { selector: "edge[kind='found_in'][tier='imported']", style: { "line-style": "dashed", "opacity": 0.6 }},
      { selector: ".faded", style: { "opacity": 0.12, "text-opacity": 0.25 }},
      { selector: "node.hl", style: { "border-width": 2, "border-color": C.ink }},
      { selector: "edge.hl", style: { "opacity": 1, "z-index": 9 }},
      { selector: "edge.hl[kind='found_in']", style: { "line-color": C.molecule, "width": 1.8 }},
      { selector: "node:selected", style: { "border-width": 4, "border-color": C.garnet, "overlay-opacity": 0 }},
      // ── Bouquet (vue d'un vin, ordinateur) : le verre en bas, les molécules montent en bulles ──
      { selector: "node.bq[type='profile']", style: { "shape": "rectangle", "width": () => 74 * SC, "height": () => 124 * SC,
        "background-opacity": 0, "border-width": 0, "background-image": (n) => glass(n.data("wine"), n.data("sparkling")),
        "background-fit": "contain", "background-clip": "none", "label": "data(label)", "text-valign": "bottom",
        "text-halign": "center", "text-margin-x": 0, "text-margin-y": () => 10 * SC, "font-family": "Fraunces, Georgia, serif",
        "font-size": () => 21 * SC, "font-weight": 600, "text-background-opacity": 0, "text-max-width": () => 380 * SC }},
      { selector: "node.bq[type='molecule']", style: { "shape": "ellipse",
        "width": (n) => bubble(n), "height": (n) => bubble(n),
        "padding": "0px", "background-color": "data(hue)", "border-width": 7, "border-color": "data(hue)", "border-opacity": 0.2,
        "label": (n) => fitBubble(n).text, "color": "#fff", "font-family": "Fraunces, Georgia, serif", "font-style": "italic",
        "font-weight": 600, "font-size": (n) => fitBubble(n).size, "text-valign": "center",
        "text-halign": "center", "text-margin-x": 0, "text-margin-y": 0, "text-wrap": "wrap",
        // Les lignes sont coupées par fitBubble ; la largeur maximale ne doit pas les recouper.
        "text-max-width": (n) => bubble(n) + 40, "text-background-opacity": 0, "line-height": LINE }},
      // Marqueur « en réserve » : la molécule du cépage, du style ou de la couleur, qu'aucun arôme cité de ce vin
      // ne trahit (l'IBMP d'un Pauillac mûr) : cercle ouvert, plus petit, à sa couleur.
      { selector: "node.bq.bouquet[type='molecule'][tier='specific'][!direct]", style: { "background-color": "data(hue)",
        "background-opacity": 0.28, "border-width": 2.5, "border-color": "data(hue)", "border-opacity": 1, "color": C.ink }},
      // Socle commun : sa couleur, adoucie (et non plus du gris).
      { selector: "node.bq.bouquet[type='molecule'][tier='universal']", style: { "background-color": "data(hue)", "background-opacity": 0.45,
        "border-color": "data(hue)", "border-opacity": 0.25, "color": C.ink }},
      { selector: "node.bq.bouquet.hl[type='molecule'][!direct]", style: { "background-color": "data(hue)", "color": "#fff" }},
      { selector: "node.bq[type='molecule'][tier='universal'], node.bq[type='molecule'][?universal]", style: {
        "background-opacity": 0.45, "color": C.ink, "border-opacity": 0.2 }},
      { selector: "node.bq[type='source'], node.bq[type='aroma']", style: { "shape": "round-rectangle", "width": "label", "height": 26,
        "padding": "9px", "background-color": "#FFFFFF", "border-width": 1.3, "border-color": "data(hue)",
        "label": "data(label)", "font-size": 12.5, "color": C.ink2, "text-valign": "center", "text-halign": "center",
        "text-margin-x": 0, "text-background-opacity": 0 }},
      // Vue d'un vin : les éléments naturels qui portent un arôme du vin sont proches et nets ; les autres
      // (la fraise du furanéol dans un tawny) restent plus haut, pâles, et s'éclairent avec leur molécule.
      { selector: "node.bq.bouquet[type='source'][?near], node.bq.bouquet[type='aroma']", style: { "border-width": 2,
        "color": C.ink, "font-weight": 500 }},
      // Arôme du vin : pastille teintée de la couleur de sa famille, pas une étiquette blanche.
      { selector: "node.bq.bouquet[type='aroma']", style: { "background-color": "data(hue)", "background-opacity": 0.2 }},
      // Arôme dominant du vin : étiquette un peu plus affirmée.
      { selector: "node.bq.bouquet[type='aroma'][intensity = 3]", style: { "font-weight": 600, "font-size": 14.5,
        "border-width": 2.8, "background-opacity": 0.32, "height": 30, "padding": "10px" }},
      { selector: "node.bq.bouquet[type='aroma'][intensity = 1]", style: { "font-size": 12, "border-width": 1.5 }},
      { selector: "node.bq.bouquet[type='source'][!near]", style: { "opacity": 0.5, "font-size": 11.5 }},
      { selector: "node.bq.bouquet.hl[type='source']", style: { "opacity": 1 }},
      { selector: "edge.bq[kind='contains']", style: { "curve-style": "unbundled-bezier",
        "source-endpoint": (e) => e.data("sep") || "outside-to-node",
        "control-point-distances": (e) => [e.data("cpd") ?? -(e.target().position("x") - e.source().position("x")) * 0.32],
        "control-point-weights": [0.55], "opacity": 0.75, "width": "mapData(strength, 1, 3, 2, 6)" }},
      { selector: "edge.bq.bouquet[kind='contains']", style: { "opacity": (e) => (e.target().data("direct") ? 0.75 : 0.3) }},
      // Molécule → élément naturel ou arôme du vin : le trait part du bord de la bulle et s'arrête net sur
      // le bord de l'étiquette (point d'arrivée calculé par placeLabels), sans pastille qui déborde ; sa
      // couleur passe de celle de la molécule à celle de l'arôme, il se fond dans l'une et dans l'autre.
      { selector: "edge.bq[kind='found_in'], edge.bq[kind='evokes']", style: { "curve-style": "unbundled-bezier",
        "control-point-distances": (e) => [e.data("cpd") || 0], "control-point-weights": [0.5],
        "source-endpoint": "outside-to-node", "target-endpoint": (e) => e.data("tep") || "outside-to-node",
        "line-cap": "round", "line-fill": "linear-gradient",
        "line-gradient-stop-colors": (e) => `${e.source().data("hue")} ${e.target().data("hue")}`,
        "line-gradient-stop-positions": "15% 85%", "source-arrow-shape": "none", "target-arrow-shape": "none" }},
      { selector: "edge.bq[kind='found_in']", style: { "opacity": 0.42, "width": "mapData(strength, 1, 3, 1.2, 3)" }},
      { selector: "edge.bq.bouquet[kind='found_in'][?near]", style: { "opacity": 0.75 }},
      { selector: "edge.bq[kind='evokes']", style: { "opacity": 0.8, "width": "mapData(strength, 1, 3, 1.4, 3.2)" }},
      // Couronne d'une molécule : la molécule en grande bulle au centre, les vins en petits verres autour.
      { selector: "node.bq[type='molecule'][?root]", style: { "width": () => 132 * SC, "height": () => 132 * SC,
        "font-size": () => 16 * SC, "text-max-width": () => 116 * SC, "border-width": 10, "border-opacity": 0.22, "label": rootLabel }},
      { selector: "node.bq.ring[type='profile']", style: { "width": 20, "height": 34, "font-family": "Inter, system-ui, sans-serif",
        "font-size": 12, "font-weight": 500, "color": C.ink, "text-valign": "center", "text-halign": "center",
        "text-margin-x": "data(lx)", "text-margin-y": "data(ly)", "text-rotation": "data(rot)", "text-wrap": "none",
        "text-background-opacity": 0 }},
      { selector: "node.bq.grid[type='profile']", style: { "width": 24, "height": 40, "font-family": "Inter, system-ui, sans-serif",
        "font-size": 11.5, "font-weight": 500, "color": C.ink, "text-valign": "bottom", "text-halign": "center",
        "text-margin-x": 0, "text-margin-y": 5, "text-rotation": 0, "text-wrap": "wrap", "text-max-width": "data(tw)",
        "text-background-opacity": 0 }},
      { selector: "node.bq[type='source'][?root]", style: { "shape": "ellipse", "width": () => 124 * SC, "height": () => 124 * SC,
        "background-color": "data(hue)", "border-width": 10, "border-color": "data(hue)", "border-opacity": 0.22,
        "label": "data(label)", "color": "#fff", "font-family": "Fraunces, Georgia, serif", "font-weight": 600,
        "font-size": () => 17 * SC, "text-wrap": "wrap", "text-max-width": () => 104 * SC, "padding": "0px" }},
      { selector: "edge.bq.grid", style: { "curve-style": "straight", "opacity": 0 }},
      { selector: "edge.bq.ring[kind='contains']", style: { "curve-style": "straight", "opacity": 0.45,
        "width": "mapData(strength, 1, 3, 1.2, 4)" }},
      { selector: "edge.bq.bouquet[kind='found_in'][!near]", style: { "opacity": 0.1 }},
      { selector: "edge.bq.minor", style: { "opacity": 0.05 }},
      { selector: "edge.bq.hl", style: { "opacity": 0.9 }},
      { selector: "node.bq:selected", style: { "border-color": C.garnet, "border-opacity": 1, "border-width": 4 }},
      { selector: "node.bq.hl[type='molecule']", style: { "border-color": "data(hue)", "border-opacity": 0.35, "border-width": 9 }},
    ],
  });

  // Le verre, dessiné aux couleurs du vin. Largeur et hauteur explicites, et dessin fait à grande
  // taille : le verre reste net quand on zoome, sans quoi il flou ou se déforme.
  const ROBE = { rouge: "#6E1A33", blanc: "#E2C766", rose: "#E89A8C" };
  const glassCache = {};
  function glass(wine, sparkling) {
    const fill = ROBE[wine] || ROBE.rouge;
    // Effervescent : une flûte, étroite et haute, avec quelques bulles qui montent.
    if (sparkling) {
      const key = `flute|${fill}`;
      if (!glassCache[key]) {
        glassCache[key] = "data:image/svg+xml;utf8," + encodeURIComponent(
          "<svg xmlns='http://www.w3.org/2000/svg' width='400' height='672' viewBox='-50 -116 100 168'>"
          + "<path d='M-22 -114 H22 C22 -60 16 -26 0 -18 C-16 -26 -22 -60 -22 -114 Z' fill='#fff' stroke='#23262F' stroke-width='2.5' stroke-linejoin='round'/>"
          + `<path d='M-20 -92 H20 C19 -56 13 -29 0 -21 C-13 -29 -19 -56 -20 -92 Z' fill='${fill}'/>`
          + "<g fill='#fff' opacity='.85'><circle cx='-6' cy='-40' r='2'/><circle cx='5' cy='-55' r='1.6'/><circle cx='-3' cy='-70' r='1.8'/><circle cx='7' cy='-82' r='1.3'/></g>"
          + "<path d='M0 -18 V40' stroke='#23262F' stroke-width='2.5'/>"
          + "<path d='M-26 46 Q0 36 26 46' fill='none' stroke='#23262F' stroke-width='2.5' stroke-linecap='round'/></svg>");
      }
      return glassCache[key];
    }
    if (!glassCache[fill]) {
      glassCache[fill] = "data:image/svg+xml;utf8," + encodeURIComponent(
        "<svg xmlns='http://www.w3.org/2000/svg' width='400' height='672' viewBox='-50 -116 100 168'>"
        + "<path d='M-46 -112 H46 C46 -58 28 -26 0 -22 C-28 -26 -46 -58 -46 -112 Z' fill='#fff' stroke='#23262F' stroke-width='2.5' stroke-linejoin='round'/>"
        + `<path d='M-43 -80 H43 C40 -50 24 -28 0 -25 C-24 -28 -40 -50 -43 -80 Z' fill='${fill}'/>`
        + "<path d='M0 -22 V40' stroke='#23262F' stroke-width='2.5'/>"
        + "<path d='M-30 46 Q0 34 30 46' fill='none' stroke='#23262F' stroke-width='2.5' stroke-linecap='round'/></svg>");
    }
    return glassCache[fill];
  }
  // Échelle des bulles : 1 sur ordinateur, un peu moins sur téléphone.
  let SC = 1;
  // Dans une bulle : le nom de la molécule en entier. Dans la vue d'un vin, l'odeur n'y figure plus :
  // elle est au bout du trait, c'est l'arôme du vin que la molécule explique. Ailleurs (soleil), la
  // première odeur précède le nom. Le nom se coupe aux espaces,
  // après un trait d'union ou après un préfixe chimique (« 2-méthyl-|butanoate »), et la taille du texte
  // baisse jusqu'à ce que chaque ligne tienne dans le cercle. Les points de suspension ne servent
  // qu'en dernier recours, sous 8,5 px.
  const PREFIXES = /(diméthyl|méthyl|méthane|éthyl|phényl|furfuryl|sulfanyl|mercapto|hydroxy|isopropyl|isobutyl|benzène|pyrrole|hexén|octén)(?=[a-zà-ÿ]{4,})/gi;
  function tokens(name) {
    // Morceaux insécables ; « sep » dit ce qui les relie : une espace, ou rien (coupure dans un mot,
    // marquée d'un trait d'union en fin de ligne si le morceau ne finit pas déjà par un).
    const out = [];
    name.split(/\s+/).forEach((word, wi) => {
      const parts = word.replace(PREFIXES, "$1\u0000").replace(/([a-zà-ÿ]{3,}-)(?=[a-zà-ÿ]{3,})/gi, "$1\u0000")
        .split("\u0000").filter(Boolean);
      parts.forEach((p, pi) => out.push({ text: p, sep: pi === 0 ? (wi === 0 ? "" : " ") : "" }));
    });
    return out;
  }
  function wrap(toks, width, measure) {
    const lines = [];
    let cur = "";
    toks.forEach((t, i) => {
      const glued = cur ? cur + t.sep + t.text : t.text;
      if (!cur || measure(glued + (toks[i + 1] && !toks[i + 1].sep && !t.text.endsWith("-") ? "-" : "")) <= width) { cur = glued; return; }
      lines.push(t.sep || cur.endsWith("-") ? cur : `${cur}-`);
      cur = t.text;
    });
    if (cur) lines.push(cur);
    return lines;
  }
  const fitCache = new Map();
  function fitBubble(n) {
    const d = bubble(n);
    return fitAt(n, d, true);
  }
  // Plancher de lisibilité : sous 11 px (et le dessin est parfois dézoomé), l'italique devient illisible ;
  // la bulle grandit plutôt que le texte ne rapetisse.
  const MIN_FS = 11;
  // Ajuste le texte à une bulle de diamètre d ; sans « last », renvoie null quand rien ne tient à MIN_FS.
  function fitAt(n, d, last) {
    const name = n.data("label") || "";
    const note = n.hasClass("bouquet") ? "" : (n.data("note") || n.data("odor") || "");
    const key = `${d}|${note}|${name}|${last ? 1 : 0}`;
    if (fitCache.has(key)) return fitCache.get(key);
    const head = note && note.toLowerCase() !== name.toLowerCase() ? [note] : [];
    const r = d / 2 - 3;
    const max = (n.data("strength") || 1) >= 3 ? 14.5 : 12.5;
    let best = null;
    for (let fs = max; fs >= MIN_FS && !best; fs -= 0.5) {
      measureCtx.font = `italic 600 ${fs}px Fraunces, Georgia, serif`;
      const measure = (t) => measureCtx.measureText(t).width;
      const room = (k, i) => {   // largeur de la corde du cercle à la hauteur de la ligne i sur k
        const y = Math.abs(i - (k - 1) / 2) * fs * LINE + fs * 0.45;
        return y >= r ? 0 : 2 * Math.sqrt(r * r - y * y);
      };
      for (let k = head.length + 1; k <= head.length + 4 && !best; k++) {
        const lines = [...head, ...wrap(tokens(name), room(k, head.length), measure)];
        if (lines.length > k) continue;
        if (lines.every((l, i) => measure(l) <= room(lines.length, i))) best = { text: lines.join("\n"), size: fs };
      }
    }
    if (!best && !last) { fitCache.set(key, null); return null; }
    if (!best) {   // dernier recours : nom sur deux lignes au plancher, la seconde abrégée
      measureCtx.font = `italic 600 ${MIN_FS}px Fraunces, Georgia, serif`;
      const measure = (t) => measureCtx.measureText(t).width;
      const lines = wrap(tokens(name), d * 0.78, measure).slice(0, 2);
      let last = lines[lines.length - 1];
      while (last.length > 3 && measure(`${last}…`) > d * 0.72) last = last.slice(0, -1);
      if (lines.join("") !== name.replace(/\s+/g, "")) lines[lines.length - 1] = `${last.replace(/-$/, "")}…`;
      best = { text: [...head, ...lines].join("\n"), size: MIN_FS };
    }
    fitCache.set(key, best);
    return best;
  }
  // Les mesures faites avant le chargement de Fraunces sont refaites avec la vraie police.
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(() => { fitCache.clear(); cy.style().update(); });
  }
  function rootLabel(n) {
    const odor = n.data("odor") || "";
    const name = n.data("label") || "";
    return odor && odor.toLowerCase() !== name.toLowerCase() ? `${odor}\n${name}` : name;
  }
  const wide = () => cy.width() >= 640;
  function bubble(n) {
    if (n.data("root")) return 132 * SC;
    if (n.data("sz")) return n.data("sz") * SC;   // taille imposée par la vue (soleil)
    // Bulles resserrées ; dans la vue d'un vin, celles qu'aucun arôme du vin ne justifie (diacétyle
    // d'un rouge, esters de fermentation…) sont plus petites encore, et grisées.
    const base = 46 + 12 * (n.data("strength") || 1);
    const indirect = n.hasClass("bouquet") && !n.data("direct");
    // Marqueur en réserve : un tiers plus petit, quelle que soit sa force ; socle commun : un peu moins.
    const shrink = !indirect ? 1 : n.data("tier") === "specific" ? 0.7 : 0.84;
    // Le poids de la molécule dans le nez : une bulle qui explique l'arôme dominant du vin (le raisin
    // frais du linalol dans un muscat) grossit ; celle d'un arôme discret (une touche de rose) rapetisse.
    let weight = 1;
    if (n.hasClass("bouquet") && !indirect) {
      const inten = Math.max(0, ...n.outgoers("node[type='aroma']").map((a) => a.data("intensity") || 1));
      weight = { 3: 1.24, 2: 1.04, 1: 0.9 }[inten] || 1;
    }
    const d = base * shrink * weight * SC;
    // Un nom long (« pyrroleméthanethiol ») agrandit un peu sa bulle plutôt que d'être abrégé.
    for (const grow of [1, 1.12, 1.25, 1.38, 1.52, 1.68]) {
      if (fitAt(n, d * grow, false)) return d * grow;
    }
    return d * 1.68;
  }
  // Une vue par point de départ : un vin en bouquet ; une molécule en couronne de vins ; un élément
  // naturel en soleil (lui au centre, ses molécules, puis leurs vins). Sur téléphone, le bouquet se
  // resserre et les deux autres deviennent une table : l'entité en haut, les vins en verres alignés.
  // Cytoscape bloque le défilement du navigateur à chaque glissé ; en vue fixe, on ne lui transmet pas les
  // mouvements du doigt (le toucher sur un nœud, lui, passe).
  let stillView = false;
  cy.container().parentElement.addEventListener("touchmove", (ev) => { if (stillView) ev.stopPropagation(); }, true);
  function layout() {
    SC = wide() ? 1 : 0.86;
    if (state.start.startsWith("profile:")) layoutBouquet(!wide());
    else if (state.start.startsWith("molecule:")) { if (wide()) layoutRing(); else layoutGrid(); }
    else if (state.start.startsWith("source:")) { if (wide()) layoutSun(); else layoutGrid(); }
    else layoutColumns();
    // Téléphone : le bouquet, la table et leurs verres tiennent dans le cadre. On rend le doigt à la
    // page : glisser fait défiler, sans déplacer ni zoomer le dessin (toucher un nœud marche toujours).
    const still = !wide() && cy.container().parentElement.classList.contains("is-bouquet");
    cy.userPanningEnabled(!still);
    cy.userZoomingEnabled(!still);
    cy.container().style.touchAction = still ? "pan-y" : "";
    stillView = still;
    cy.style().update();
  }
  let ownResize = 0;
  function prepare(height, classes) {
    const canvas = cy.container().parentElement;
    ownResize = Date.now();
    canvas.classList.add("is-bouquet");
    const want = `${Math.round(height)}px`;
    if (canvas.style.minHeight !== want) { canvas.style.minHeight = want; cy.resize(); }
    cy.elements().removeClass("bq ring grid bouquet").addClass(`bq ${classes}`);
    cy.nodes().removeClass("compact");
  }
  const byColour = { rouge: 0, rose: 1, blanc: 2 };
  function strengthOf(w) {
    return Math.max(0, ...w.connectedEdges("[kind='contains']").map((e) => e.data("strength") || 0));
  }
  function sortWines(list) {
    return list.sort((a, b) => (byColour[a.data("wine")] ?? 3) - (byColour[b.data("wine")] ?? 3)
      || strengthOf(b) - strengthOf(a) || (a.data("label") || "").localeCompare(b.data("label") || ""));
  }
  // Noms des vins en rayons autour d'un cercle, lisibles de gauche à droite.
  function radialLabel(w, a) {
    const rad = (d) => (d * Math.PI) / 180;
    const ux = Math.sin(rad(a)), uy = -Math.cos(rad(a));
    measureCtx.font = "500 12px Inter, system-ui, sans-serif";
    const off = measureCtx.measureText(w.data("label") || "").width / 2 + 18;
    let rot = Math.atan2(uy, ux);
    if (ux < 0) rot += Math.PI;
    w.data({ lx: ux * off, ly: uy * off, rot });
    return { ux, uy };
  }
  // Étiquettes en rangées centrées (éléments naturels), retour à la ligne quand la largeur est pleine.
  function rowsOf(nodes, top, W, gapY = 50) {
    measureCtx.font = "400 12.5px Inter, system-ui, sans-serif";
    const out = {};
    let row = [], width = 0, y = top;
    const flush = () => {
      let x = W / 2 - width / 2;
      row.forEach(({ n, w }) => { out[n.id()] = { x: x + w / 2, y }; x += w + 10; });
      row = []; width = 0; y += gapY;
    };
    nodes.forEach((n) => {
      const w = measureCtx.measureText(n.data("label") || "").width + 30;
      if (row.length && width + w + 10 > W - 24) flush();
      width += (row.length ? 10 : 0) + w;
      row.push({ n, w });
    });
    if (row.length) flush();
    return { positions: out, bottom: y - gapY };
  }

  // ── Couronne : une molécule au centre, ses vins en verres tout autour (par couleur), sa nature au-dessus ──
  function layoutRing() {
    const R0 = Math.max(170, Math.min(cy.width() / 2 - 150, 330));
    // Au-dessus : la nature (0,86 R) ; en dessous : le cercle et les noms qui en partent (≈ 190 px).
    prepare(1.86 * R0 + 260, "ring");
    const W = cy.width(), H = cy.height();
    const rad = (d) => (d * Math.PI) / 180;
    const cx = W / 2, R = R0;
    const cyy = Math.max(0.86 * R + 50, H - R - 200);
    const positions = {};
    cy.nodes("[type='molecule']").forEach((m) => { positions[m.id()] = { x: cx, y: cyy }; });
    // Les vins sur l'arc du bas (de 62° à 298°) : le haut est laissé à la nature.
    const list = sortWines(cy.nodes("[type='profile']").toArray());
    const n = list.length;
    list.forEach((w, k) => {
      const a = n > 1 ? 62 + (236 * k) / (n - 1) : 180;
      const { ux, uy } = radialLabel(w, a);
      positions[w.id()] = { x: cx + R * ux, y: cyy + R * uy };
    });
    // La nature : deux rangées en quinconce dans l'éventail du haut.
    const srcs = cy.nodes("[type='source']").toArray();
    const rows = [srcs.filter((_s, k) => k % 2 === 0), srcs.filter((_s, k) => k % 2 === 1)];
    rows.forEach((row, r) => Object.assign(positions, rowsOf(row, cyy - R * (r ? 0.62 : 0.86), W).positions));
    run(positions, false);
  }

  // ── Soleil : un élément naturel au centre, ses molécules autour, leurs vins en couronne ──
  function layoutSun() {
    const R0 = Math.max(170, Math.min(cy.width() / 2 - 175, 320));
    prepare(2 * R0 + 400, "ring");
    const W = cy.width(), H = cy.height();
    const rad = (d) => (d * Math.PI) / 180;
    const cx = W / 2, cyy = H / 2 + 10, R = R0;
    const positions = {};
    const source = cy.nodes("[type='source']");
    const mols = cy.nodes("[type='molecule']").toArray();
    // Chaque vin n'est relié qu'à sa molécule principale (lien le plus fort) ; les autres liens
    // restent là, très pâles, et s'allument au survol : sinon, toile d'araignée.
    const main = {};
    cy.edges("[kind='contains']").removeClass("minor");
    cy.nodes("[type='profile']").forEach((w) => {
      const es = w.connectedEdges("[kind='contains']").sort((a, b) => (b.data("strength") || 0) - (a.data("strength") || 0));
      main[w.id()] = es[0] ? es[0].target().id() : null;
      es.slice(1).addClass("minor");
    });
    cy.nodes("[type='molecule']").removeData("sz");
    if (mols.length === 1) {
      mols[0].data("sz", 112);
      // Une seule molécule (poivre noir → rotundone) : elle au centre, l'élément naturel au-dessus,
      // les vins en arc dessous, comme la couronne d'une molécule.
      positions[mols[0].id()] = { x: cx, y: cyy };
      source.forEach((s) => { positions[s.id()] = { x: cx, y: cyy - R * 0.78 }; });
      const list = sortWines(cy.nodes("[type='profile']").toArray());
      const n = list.length;
      list.forEach((w, k) => {
        const a = n > 1 ? 62 + (236 * k) / (n - 1) : 180;
        const { ux, uy } = radialLabel(w, a);
        positions[w.id()] = { x: cx + R * ux, y: cyy + R * uy };
      });
      run(positions, false);
      return;
    }
    source.forEach((s) => { positions[s.id()] = { x: cx, y: cyy }; });
    // Un secteur par molécule, proportionné au nombre de vins dont elle est la molécule principale.
    const groups = mols.map((m) => ({ m, wines: sortWines(cy.nodes("[type='profile']").filter((w) => main[w.id()] === m.id()).toArray()) }))
      .sort((p, q) => q.wines.length - p.wines.length);
    // Les molécules qui portent le plus de vins d'abord ; leur bulle grandit avec ce nombre.
    groups.forEach((g) => g.m.data("sz", 64 + 6 * Math.min(g.wines.length, 6)));
    const nw = groups.reduce((t, g) => t + g.wines.length, 0);
    const r1 = Math.max(130, R * 0.52);
    // Chaque secteur est assez large pour sa bulle, et pour ses vins espacés d'au moins 8°.
    const need = (g) => Math.max((((g.m.data("sz") + 22) / r1) * 180) / Math.PI, g.wines.length * 8);
    const sum = groups.reduce((t, g) => t + need(g), 0);
    let a0 = 0;
    groups.forEach((g) => {
      const span = (need(g) * 360) / sum;
      const mid = a0 + span / 2;
      positions[g.m.id()] = { x: cx + r1 * Math.sin(rad(mid)), y: cyy - r1 * Math.cos(rad(mid)) };
      const k = g.wines.length;
      g.wines.forEach((w, i) => {
        const a = a0 + (span * (i + 0.5)) / k;
        const { ux, uy } = radialLabel(w, a);
        positions[w.id()] = { x: cx + R * ux, y: cyy + R * uy };
      });
      a0 += span;
    });
    run(positions, false);
  }

  // ── Table (téléphone) : l'entité en haut, ses molécules s'il y a lieu, puis les vins alignés ──
  function layoutGrid() {
    const W = cy.width();
    const root = cy.nodes("[?root]");
    const mols = root.data("type") === "source" ? cy.nodes("[type='molecule']").toArray() : [];
    const wines = sortWines(cy.nodes("[type='profile']").toArray());
    const perRow = 4, molRows = Math.ceil(mols.length / perRow);
    const cols = 3, cellW = (W - 16) / cols, cellH = 92;
    const others = root.data("type") === "molecule" ? cy.nodes("[type='source']").toArray() : [];
    const srcRows = others.length ? rowsOf(others, 0, W, 50) : null;
    // Molécule au centre : sa nature d'abord, juste sous elle (plus lisible), puis les vins.
    const srcH = srcRows ? srcRows.bottom + 70 : 0;
    const wineTop = 170 + (molRows ? molRows * 92 + 10 : 0) + srcH;
    prepare(wineTop + Math.ceil(wines.length / cols) * cellH + 30, "grid");
    const positions = {};
    positions[root.id()] = { x: W / 2, y: 86 };
    mols.forEach((m, k) => {
      const row = Math.floor(k / perRow), inRow = Math.min(perRow, mols.length - row * perRow);
      positions[m.id()] = { x: W / 2 + ((k % perRow) - (inRow - 1) / 2) * (W / perRow), y: 210 + row * 92 };
    });
    wines.forEach((w, k) => {
      const row = Math.floor(k / cols), col = k % cols;
      w.data({ tw: cellW - 10 });
      positions[w.id()] = { x: 8 + cellW * (col + 0.5), y: wineTop + row * cellH };
    });
    if (srcRows) {
      const y0 = 170;
      Object.entries(srcRows.positions).forEach(([id, p]) => { positions[id] = { x: p.x, y: p.y + y0 }; });
    }
    run(positions, false);
  }

  // ── Bouquet : le vin en bas, ses molécules en éventail au-dessus, et contre chaque bulle l'arôme
  // du vin qu'elle explique (une étiquette partagée se pose entre ses bulles) ──
  function layoutBouquet(compact = false) {
    const positions = {};
    // Téléphone : le cadre grandit avec le nombre de bulles (la page défile), sinon tout se tasse.
    const n = cy.nodes("[type='molecule']").length;
    prepare(compact ? 760 + 52 * Math.max(0, n - 5) : 820, "bouquet");
    placeBubbles(positions, compact ? 96 : 110, compact);
  }
  // Les copies d'étiquettes d'une mise en page précédente rejoignent leur original.
  function unsplitLabels() {
    cy.nodes("[of]").forEach((twin) => {
      twin.incomers("edge").forEach((e) => {
        const d = { ...e.data(), id: e.id().replace(/~\d+$/, ""), target: twin.data("of") };
        const cls = e.classes();
        cy.remove(e);
        cy.add({ group: "edges", data: d, classes: cls });
      });
      cy.remove(twin);
    });
  }
  function placeBubbles(positions, topLimit, compact) {
    unsplitLabels();
    const W = cy.width(), H = cy.height();
    const rad = (d) => (d * Math.PI) / 180;
    const ox = W / 2, oy = H - (compact ? 190 : 230);
    cy.nodes("[type='profile']").forEach((n) => { positions[n.id()] = { x: ox, y: H - (compact ? 110 : 150) }; });
    // Molécules : les plus sûres au centre, en quinconce sur deux ou trois anneaux.
    // Les bulles qui expliquent le même arôme du vin (vanilline et whisky-lactone → vanille) sont voisines :
    // leur étiquette commune tombe entre elles, sans trait en travers du bouquet. Les groupes les plus forts
    // au centre, puis en alternance à droite et à gauche.
    const sorted = cy.nodes("[type='molecule']").sort((a, b) => (b.data("strength") || 0) - (a.data("strength") || 0)
      || (a.data("universal") ? 1 : 0) - (b.data("universal") ? 1 : 0)).toArray();
    const groupOf = (m) => {
      const labels = m.outgoers("node[type='aroma']").map((x) => x.id()).sort();
      return labels.length ? labels[0] : m.id();
    };
    const groups = [];
    const index = new Map();
    sorted.forEach((m) => {
      // Une molécule rejoint le groupe d'un de ses arômes déjà ouvert, sinon en ouvre un.
      const keys = m.outgoers("node[type='aroma']").map((x) => x.id());
      const hit = keys.find((k) => index.has(k));
      const g = hit !== undefined ? index.get(hit) : (groups.push([]), groups[groups.length - 1]);
      g.push(m);
      [groupOf(m), ...keys].forEach((k) => { if (!index.has(k)) index.set(k, g); });
    });
    const row = [];
    groups.forEach((g, i) => { if (i % 2) row.unshift(...g); else row.push(...g); });
    const mols = cy.collection(row);
    const n = row.length;
    const slots = [...Array(n).keys()];
    // Hauteur : d'où vient la molécule, du plus loin au plus près du verre. Le raisin (et la vigne) en haut,
    // la fermentation au milieu, l'élevage et l'âge contre le verre.
    const ringOf = { 1: 1, 2: n > 9 ? 0.78 : 0.72, 3: n > 9 ? 0.56 : 0.5 };
    const band = { raisin: 1, precurseur: 1, environnement: 1, fermentation: 2, malolactique: 2, micro: 2, bois: 3, vieillissement: 3 };
    const rx = compact ? W * 0.4 : Math.min(W * 0.4, 360);
    // Le haut du cadre garde la place des étiquettes d'arômes posées au-dessus des bulles.
    const ry = compact ? Math.max(120, (oy - topLimit) * 0.86) : Math.min((oy - topLimit) * 0.84, 430);
    const spanM = Math.min(140, 40 + n * 14);
    // Un anneau chargé (cinq molécules du raisin dans un Gewurztraminer) s'étage en quinconce.
    const perBand = {};
    row.forEach((m) => { const b = band[m.data("origin")] || 2; perBand[b] = (perBand[b] || 0) + 1; });
    // Les anneaux occupent toute la hauteur : un vin sans molécule du raisin (Pouilly-Fuissé, porto) ne
    // laisse pas le haut du cadre vide ; l'ordre raisin, fermentation, élevage est gardé.
    const used = Object.keys(perBand).map(Number).sort();
    const spread = used.length === 1 ? [0.86] : used.length === 2 ? [1, n > 9 ? 0.66 : 0.6] : [1, ringOf[2], ringOf[3]];
    used.forEach((b, i) => { ringOf[b] = spread[i]; });
    const seen = {};
    row.forEach((m, k) => {
      const slot = slots[k];
      const a = n > 1 ? -spanM / 2 + (spanM * slot) / (n - 1) : 0;
      const b = band[m.data("origin")] || 2;
      seen[b] = (seen[b] || 0) + 1;
      const stagger = perBand[b] > 3 && seen[b] % 2 === 0 ? (compact ? 0.14 : 0.1) : 0;
      const ring = ringOf[b] - stagger;
      positions[m.id()] = { x: ox + rx * ring * Math.sin(rad(a)), y: oy - ry * ring * Math.cos(rad(a)) };
    });
    // Les bulles ne se touchent pas : on les écarte deux à deux (au-dessus du verre, dans le cadre).
    const size = (m) => bubble(m) / 2;
    const ms = mols.toArray();
    for (let it = 0; it < 90; it++) {
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
      // Une bulle ne cache pas la tige d'une bulle plus haute : on l'écarte de côté (le bouquet s'ouvre).
      if (it < 45) {
        for (let i = 0; i < ms.length; i++) {
          for (let j = 0; j < ms.length; j++) {
            if (i === j) continue;
            const hi = positions[ms[i].id()], lo = positions[ms[j].id()];
            if (lo.y <= hi.y) continue;
            const gx = ox, gy = oy + 40;   // pied des tiges, au bord du verre
            const dx = hi.x - gx, dy = hi.y - gy, L2 = dx * dx + dy * dy || 1;
            const t = ((lo.x - gx) * dx + (lo.y - gy) * dy) / L2;
            if (t <= 0.05 || t >= 1) continue;
            const px = gx + t * dx, py = gy + t * dy, d = Math.hypot(lo.x - px, lo.y - py) || 0.01;
            const need = size(ms[j]) + 10;
            if (d >= need) continue;
            const ux = (lo.x - px) / d || (lo.x >= ox ? 1 : -1), push = Math.min(need - d, 12);
            lo.x += ux * push * 0.7; hi.x -= ux * push * 0.3;
            moved = true;
          }
        }
      }
      ms.forEach((m) => {
        const p = positions[m.id()], r = size(m);
        p.x = Math.min(W - r - 10, Math.max(r + 10, p.x));
        p.y = Math.min(oy - r + 10, Math.max(r + topLimit, p.y));
      });
      if (!moved) break;
    }
    splitFarLabels(positions, compact ? W * 0.42 : 250);
    const stems = routeStems(positions);
    const labels = () => cy.nodes("[type='aroma'], [type='source']").toArray();
    placeLabels(positions, labels(), ox, oy, compact ? 22 : 26, compact ? 36 : 22, stems);
    // Deux copies d'une même étiquette posées côte à côte redeviennent une seule (en faisceau).
    if (mergeNearTwins(positions)) placeLabels(positions, labels(), ox, oy, compact ? 22 : 26, compact ? 36 : 22, stems);
    routeEdges(positions);
    trimTop(positions);
    run(positions, false);
  }
  // Étiquettes d'arômes : chacune dans l'axe de ses bulles vu du verre (angle moyen), posée juste au-delà
  // du bord du bouquet dans cette direction ; puis on les écarte des bulles et entre elles. Les traits
  // partent vers l'extérieur et ne traversent pas le dessin.
  // Une étiquette partagée par des bulles éloignées (la rose du nérol, en haut à gauche, et du
  // 2-phényléthanol, en bas à droite) tirait des traits à travers tout le bouquet : on la répète, une
  // par groupe de bulles voisines. Les bulles proches gardent une étiquette commune, en faisceau.
  // La copie porte l'identifiant de l'original dans « of » (fiche, surbrillance).
  function splitFarLabels(positions, reach) {
    cy.nodes("[type='aroma'], [type='source']").forEach((lab) => {
      const ms = lab.incomers("node[type='molecule']").filter((m) => positions[m.id()]).toArray();
      if (ms.length < 2) return;
      // Groupes par lien complet : toutes les bulles d'un groupe sont à moins de « reach » les unes des autres.
      const groups = [];
      ms.sort((a, b) => positions[a.id()].x - positions[b.id()].x).forEach((m) => {
        const p = positions[m.id()];
        const g = groups.find((gr) => gr.every((o) => Math.hypot(positions[o.id()].x - p.x, positions[o.id()].y - p.y) <= reach));
        if (g) g.push(m); else groups.push([m]);
      });
      groups.slice(1).forEach((g, i) => {
        const id = `${lab.id()}~${i + 1}`;
        cy.add({ group: "nodes", data: { ...lab.data(), id, of: lab.id() }, classes: lab.classes() });
        g.forEach((m) => m.edgesTo(lab).forEach((e) => {
          const d = { ...e.data(), id: `${e.id()}~${i + 1}`, target: id };
          const cls = e.classes();
          cy.remove(e);
          cy.add({ group: "edges", data: d, classes: cls });
        }));
      });
    });
  }
  function mergeNearTwins(positions) {
    let merged = false;
    cy.nodes("[of]").forEach((twin) => {
      const orig = cy.getElementById(twin.data("of"));
      const a = positions[twin.id()], b = positions[orig.id()];
      if (!a || !b || Math.hypot(a.x - b.x, a.y - b.y) > labelBox(orig).hw * 2 + 70) return;
      twin.incomers("edge").forEach((e) => {
        const d = { ...e.data(), id: e.id().replace(/~\d+$/, ""), target: orig.id() };
        const cls = e.classes();
        cy.remove(e);
        cy.add({ group: "edges", data: d, classes: cls });
      });
      cy.remove(twin);
      delete positions[twin.id()];
      merged = true;
    });
    return merged;
  }
  // Pas de grand vide en haut du cadre : tout remonte et le cadre raccourcit d'autant.
  function trimTop(positions) {
    let top = Infinity;
    cy.nodes().forEach((n) => {
      const p = positions[n.id()];
      if (!p) return;
      const half = n.data("type") === "molecule" ? bubble(n) / 2 + 7
        : n.data("type") === "profile" ? 62 * SC : labelBox(n).hh;
      top = Math.min(top, p.y - half);
    });
    const cut = Math.max(0, Math.floor(top - 28));
    Object.values(positions).forEach((p) => { p.y -= cut; });
    // En bas : le nom du vin sous le verre, sur deux ou trois lignes s'il est long.
    let bottom = 0;
    cy.nodes("[type='profile']").forEach((g) => {
      const p = positions[g.id()];
      if (!p) return;
      measureCtx.font = `600 ${21 * SC}px Fraunces, Georgia, serif`;
      const lines = wrap(tokens(g.data("label") || ""), 380 * SC, (t) => measureCtx.measureText(t).width).length;
      bottom = Math.max(bottom, p.y + 62 * SC + 10 * SC + lines * 21 * SC * 1.3);
    });
    const height = Math.round(Math.max(bottom + 26, 420));
    const canvas = cy.container().parentElement;
    if (Math.abs(height - cy.height()) < 2) return;
    ownResize = Date.now();
    canvas.style.minHeight = `${height}px`;
    cy.resize();
  }
  // Demi-taille réelle d'une étiquette (texte, marge intérieure, bordure), selon son poids dans le nez.
  function labelBox(s) {
    const strong = s.data("type") === "aroma" && s.data("intensity") === 3;
    const weak = s.data("type") === "aroma" && s.data("intensity") === 1;
    measureCtx.font = strong ? "600 14.5px Inter, system-ui, sans-serif" : `500 ${weak ? 12 : 12.5}px Inter, system-ui, sans-serif`;
    const pad = strong ? 10 : 9, h = strong ? 30 : 26, border = strong ? 2.8 : 2;
    return { hw: measureCtx.measureText(s.data("label") || "").width / 2 + pad + border, hh: h / 2 + pad + border / 2 };
  }
  // ── Géométrie partagée par le placement des étiquettes et le tracé des traits ──
  // Courbe de Bézier quadratique comme Cytoscape la trace (point de contrôle à « w » du trait, décalé de
  // « d » sur la normale), échantillonnée.
  function curve(s, t, d, w, k = 24) {
    const L = Math.hypot(t.x - s.x, t.y - s.y) || 1, nx = -(t.y - s.y) / L, ny = (t.x - s.x) / L;
    const c = { x: s.x + (t.x - s.x) * w + nx * d, y: s.y + (t.y - s.y) * w + ny * d };
    const pts = [];
    for (let i = 0; i <= k; i++) {
      const u = i / k, v = 1 - u;
      pts.push({ x: v * v * s.x + 2 * v * u * c.x + u * u * t.x, y: v * v * s.y + 2 * v * u * c.y + u * u * t.y });
    }
    return pts;
  }
  // Le segment a → b coupe-t-il la ligne brisée pts ?
  function crossesPath(a, b, pts) {
    const cr = (p, q, r) => (q.x - p.x) * (r.y - p.y) - (q.y - p.y) * (r.x - p.x);
    for (let i = 0; i < pts.length - 1; i++) {
      const c = pts[i], d = pts[i + 1];
      if (cr(a, b, c) * cr(a, b, d) < 0 && cr(c, d, a) * cr(c, d, b) < 0) return true;
    }
    return false;
  }
  const inBox = (p, b, pad) => Math.abs(p.x - b.x) < b.hw + pad && Math.abs(p.y - b.y) < b.hh + pad;
  const boxHitsCircle = (b, c, pad) => {
    const qx = Math.max(b.x - b.hw, Math.min(c.x, b.x + b.hw)), qy = Math.max(b.y - b.hh, Math.min(c.y, b.y + b.hh));
    return Math.hypot(qx - c.x, qy - c.y) < c.r + pad;
  };
  // Les tiges sortent de la surface du vin, réparties sur la largeur du verre dans l'ordre de leurs
  // bulles (de gauche à droite) : un bouquet qui s'ouvre, et non un faisceau qui part d'un point.
  // Chaque tige garde sa courbe naturelle tant qu'elle ne passe derrière aucune bulle ; sinon elle se
  // courbe juste assez pour la contourner.
  function routeStems(positions) {
    const stems = [];
    const mols = cy.nodes("[type='molecule']").map((m) => ({ id: m.id(), ...positions[m.id()], r: bubble(m) / 2 + 5 }));
    cy.nodes("[type='profile']").forEach((g) => {
      const gp = positions[g.id()];
      if (!gp) return;
      const es = g.connectedEdges("[kind='contains']").filter((e) => positions[e.target().id()]).toArray()
        .sort((e1, e2) => Math.atan2(positions[e1.target().id()].x - gp.x, gp.y - positions[e1.target().id()].y)
          - Math.atan2(positions[e2.target().id()].x - gp.x, gp.y - positions[e2.target().id()].y));
      const k = es.length, half = 30 * SC, depth = -44 * SC;
      es.forEach((e, i) => {
        const dx = k > 1 ? -half + (2 * half * i) / (k - 1) : 0;
        e.data("sep", `${dx.toFixed(1)}px ${depth.toFixed(1)}px`);
        const s = { x: gp.x + dx, y: gp.y - 62 * SC };
        const m = positions[e.target().id()];
        const natural = -(m.x - s.x) * 0.3;
        const cost = (d) => {
          const pts = curve(s, m, d, 0.55);
          let n = 0;
          mols.forEach((b) => { if (b.id !== e.target().id() && pts.some((p) => Math.hypot(p.x - b.x, p.y - b.y) < b.r)) n += 1; });
          if (pts.some((p) => p.x < 6 || p.x > cy.width() - 6)) n += 2;
          return n;
        };
        let pick = natural, score = cost(natural) * 1000;
        for (let step = 5; score && step <= 160; step += 5) {
          for (const sg of [-1, 1]) {
            const sc = cost(natural + sg * step) * 1000 + step;
            if (sc < score) { score = sc; pick = natural + sg * step; }
          }
        }
        e.data("cpd", pick);
        stems.push({ id: e.target().id(), pts: curve(s, m, pick, 0.55, 16) });
      });
    });
    return stems;
  }
  // Traits molécule → étiquette : droits si rien ne les gêne, sinon courbés juste assez.
  function routeEdges(positions) {
    const mols = cy.nodes("[type='molecule']").map((m) => ({ id: m.id(), ...positions[m.id()], r: bubble(m) / 2 + 4 }));
    const boxes = cy.nodes("[type='aroma'], [type='source']").filter((n) => positions[n.id()])
      .map((n) => ({ id: n.id(), ...positions[n.id()], ...labelBox(n) }));
    cy.edges("[kind='evokes'], [kind='found_in']").forEach((e) => {
      const m = positions[e.source().id()], a = positions[e.target().id()];
      if (!m || !a) return;
      const skip = new Set([e.source().id(), e.target().id()]);
      const cost = (d) => {
        const pts = curve(m, a, d, 0.5);
        let n = 0;
        mols.forEach((b) => { if (!skip.has(b.id) && pts.some((p) => Math.hypot(p.x - b.x, p.y - b.y) < b.r)) n += 1; });
        boxes.forEach((b) => { if (!skip.has(b.id) && pts.some((p) => inBox(p, b, 3))) n += 2; });
        if (pts.some((p) => p.x < 4 || p.x > cy.width() - 4 || p.y < 4)) n += 3;
        return n;
      };
      let pick = 0, score = cost(0) * 1000;
      for (let step = 6; score && step <= 120; step += 6) {
        for (const sg of [-1, 1]) {
          const sc = cost(sg * step) * 1000 + step;
          if (sc < score) { score = sc; pick = sg * step; }
        }
      }
      e.data("cpd", pick);
    });
  }
  // Étiquettes d'arômes : chacune cherche, autour de ses bulles, la place libre la plus proche (vers
  // l'extérieur du bouquet de préférence) : sans chevaucher bulle, étiquette ni tige, et sans que ses
  // traits ou ceux des autres passent sous une étiquette ou derrière une bulle. Les arômes dominants,
  // puis les étiquettes reliées à plusieurs bulles, choisissent d'abord.
  function placeLabels(positions, labels, ox, oy, topMin, gap = 22, stems = []) {
    const W = cy.width();
    const bubbles = cy.nodes("[type='molecule']").map((m) => ({ id: m.id(), ...positions[m.id()], r: bubble(m) / 2 + 7 }));
    const items = labels.map((s) => {
      const ms = s.incomers("node[type='molecule']").toArray().filter((m) => positions[m.id()]);
      return { s, ms: ms.map((m) => ({ id: m.id(), ...positions[m.id()], r: bubble(m) / 2 + 7 })), ...labelBox(s) };
    }).sort((a, b) => (b.s.data("intensity") || 0) - (a.s.data("intensity") || 0) || b.ms.length - a.ms.length);
    const placed = [];
    const seg = (p, q, k = 14) => [...Array(k + 1).keys()].map((i) => ({ x: p.x + ((q.x - p.x) * i) / k, y: p.y + ((q.y - p.y) * i) / k }));
    items.forEach((it) => {
      const c = it.ms.length
        ? { x: it.ms.reduce((t, m) => t + m.x, 0) / it.ms.length, y: it.ms.reduce((t, m) => t + m.y, 0) / it.ms.length }
        : { x: ox, y: topMin + 60 };
      const out = Math.atan2(c.x - ox, oy - c.y);
      const reach = Math.max(...it.ms.map((m) => Math.hypot(m.x - c.x, m.y - c.y) + m.r), 30);
      let best = null;
      for (let dt = 0; dt <= 180; dt += 12) {
        for (const sg of dt ? [-1, 1] : [1]) {
          const a = out + (sg * dt * Math.PI) / 180;
          for (const extra of [10, 26, 48, 76, 110, 150, 200]) {
            const dist = reach + extra + it.hh * Math.abs(Math.cos(a)) + it.hw * Math.abs(Math.sin(a)) * 0.9;
            const cand = { x: c.x + dist * Math.sin(a), y: c.y - dist * Math.cos(a), hw: it.hw, hh: it.hh };
            if (cand.x - cand.hw < 6 || cand.x + cand.hw > W - 6 || cand.y - cand.hh < topMin || cand.y + cand.hh > oy - 50) continue;
            let k = 0;
            if (bubbles.some((b) => boxHitsCircle(cand, b, 4))) continue;
            if (placed.some((o) => Math.abs(o.x - cand.x) < o.hw + cand.hw + 8 && Math.abs(o.y - cand.y) < o.hh + cand.hh + 6)) continue;
            // Ses traits : derrière une autre bulle, sous une étiquette déjà posée.
            it.ms.forEach((m) => {
              const line = seg(m, cand);
              bubbles.forEach((b) => { if (b.id !== m.id && line.some((p) => Math.hypot(p.x - b.x, p.y - b.y) < b.r - 3)) k += 300; });
              placed.forEach((o) => { if (line.some((p) => inBox(p, o, 4))) k += 400; });
              // Un trait qui barre les tiges des autres bulles brouille le bouquet.
              stems.forEach((st) => { if (st.id !== m.id && crossesPath(m, cand, st.pts)) k += 220; });
              // Ni les traits des autres étiquettes.
              placed.forEach((o) => o.ms.forEach((m2) => { if (m2.id !== m.id && crossesPath(m, cand, [m2, o])) k += 220; }));
              k += Math.hypot(cand.x - m.x, cand.y - m.y) * 0.6;
            });
            // Les traits des étiquettes déjà posées ne passent pas sous celle-ci.
            placed.forEach((o) => o.ms.forEach((m) => { if (seg(m, o).some((p) => inBox(p, cand, 4))) k += 400; }));
            // Pas sur une tige.
            stems.forEach((st) => { if (st.pts.some((p) => inBox(p, cand, 3))) k += 400; });
            k += dt * 0.8 + (cand.y > c.y ? 120 : 0);
            if (!best || k < best.k) best = { ...cand, k };
          }
        }
      }
      if (!best) best = { x: Math.min(W - it.hw - 6, Math.max(it.hw + 6, c.x)), y: topMin + it.hh, k: 0 };
      it.x = best.x; it.y = best.y;
      placed.push(it);
    });
    items.forEach((a) => { positions[a.s.id()] = { x: a.x, y: a.y }; });
    // Point d'arrivée sur le bord de l'étiquette : en bas (ou en haut) si les bulles sont sous (ou sur)
    // l'étiquette, sur le côté si elles sont à sa hauteur. Plusieurs traits vers une même étiquette
    // (« rose » de quatre molécules) se rejoignent en un seul point : un faisceau qui se fond dans l'arôme.
    items.forEach((a) => {
      const es = a.s.connectedEdges("[kind='evokes'], [kind='found_in']").toArray()
        .filter((e) => positions[e.source().id()]);
      if (!es.length) return;
      const vx = es.reduce((t, e) => t + positions[e.source().id()].x - a.x, 0) / es.length;
      const vy = es.reduce((t, e) => t + positions[e.source().id()].y - a.y, 0) / es.length;
      let dx, dy;
      if (Math.abs(vy) * a.hw >= Math.abs(vx) * a.hh) {
        dx = Math.max(-a.hw + 14, Math.min(a.hw - 14, (vx * a.hh) / Math.abs(vy)));
        dy = Math.sign(vy) * a.hh;
      } else {
        dx = Math.sign(vx) * a.hw;
        dy = Math.max(-a.hh + 10, Math.min(a.hh - 10, (vy * a.hw) / Math.abs(vx)));
      }
      // Un demi-pixel à l'intérieur : le trait touche la bordure, sans jour ni débord.
      dx -= Math.sign(dx) * 0.5; dy -= Math.sign(dy) * 0.5;
      es.forEach((e) => e.data("tep", `${dx.toFixed(1)}px ${dy.toFixed(1)}px`));
    });
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
    cy.elements().removeClass("bq ring grid");
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

  let lastLayout = null;
  let printing = false;
  function run(positions, fit) {
    cy.zoom(1);
    cy.pan({ x: 0, y: 0 });
    // Une mise en page encore en cours (cadre redimensionné) s'arrête ; un nœud tout juste ajouté
    // (étiquette répétée) se pose d'emblée à sa place au lieu de partir du coin du cadre.
    if (lastLayout) lastLayout.stop();
    cy.nodes().forEach((n) => {
      const p = positions[n.id()];
      if (p && n.position("x") === 0 && n.position("y") === 0) n.position(p);
    });
    lastLayout = cy.layout({
      name: "preset", positions: (n) => positions[n.id()], fit, padding: 50,
      animate: !reduceMotion && !printing, animationDuration: 380,
    });
    lastLayout.run();
    if (!fit) keepInView(positions);
    placeColumnLabels();
  }
  // Couronne, soleil, bouquet : dessinés pour leur cadre, mais un long nom de vin ou une étiquette poussée
  // au bord peut déborder (« Muscat de Beaumes-de-Venise blanc » coupé). On dézoome juste assez, jamais
  // au-delà de 1, d'après les positions d'arrivée (l'animation n'est pas finie quand on décide).
  function keepInView(positions) {
    let x1 = Infinity, x2 = -Infinity, y1 = Infinity, y2 = -Infinity;
    cy.nodes().forEach((n) => {
      const to = positions[n.id()];
      if (!to) return;
      const at = n.position(), bb = n.boundingBox({ includeLabels: true });
      x1 = Math.min(x1, to.x + bb.x1 - at.x); x2 = Math.max(x2, to.x + bb.x2 - at.x);
      y1 = Math.min(y1, to.y + bb.y1 - at.y); y2 = Math.max(y2, to.y + bb.y2 - at.y);
    });
    if (!Number.isFinite(x1)) return;
    const W = cy.width(), H = cy.height(), pad = 14;
    if (x1 >= pad && x2 <= W - pad && y1 >= pad && y2 <= H - pad) return;
    const zoom = Math.min(1, (W - 2 * pad) / (x2 - x1), (H - 2 * pad) / (y2 - y1));
    // Dézoomé, le dessin reste centré ; à 1, on ne le décale que de ce qui dépasse.
    const cxm = (x1 + x2) / 2, cym = (y1 + y2) / 2;
    const nudge = (lo, hi, size) => Math.min(0, size - pad - hi) + Math.max(0, pad - lo);
    cy.viewport(zoom < 1
      ? { zoom, pan: { x: W / 2 - zoom * cxm, y: H / 2 - zoom * cym } }
      : { zoom: 1, pan: { x: nudge(x1, x2, W), y: nudge(y1, y2, H) } });
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
    // Nouveau vin : l'âge et « Voir tout » repartent de zéro (l'âge par défaut suit la garde du vin).
    if (id !== state.start) { state.age = null; state.everything = false; }
    const mine = ++seq;
    stats.textContent = _("Chargement…");
    let data;
    try {
      const more = kind === "molecule" || kind === "source" ? "&vins=32" : "";
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
    renderWine(data, kind);
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
    if (kind === "molecule") parts.push(plural(_("%s élément naturel"), _("%s éléments naturels"), s.sources));
    let text = parts.join(", ") + ".";
    // Ce que la chimie explique, et ce qu'elle n'explique pas encore : « 4 arômes sur 9 ».
    if (kind === "profile" && s.aromas_total) {
      text += " " + _("Arômes du vin expliqués : %a sur %t.").replace("%a", s.aromas).replace("%t", s.aromas_total);
    }
    if (!s.molecules && kind === "profile") text = _("Aucune molécule spécifique pour ce vin dans nos sources.");
    if (s.hidden_common) text += " " + plural(_("%s lien masqué (socle commun)."), _("%s liens masqués (socle commun)."), s.hidden_common);
    else if (s.common && !state.common && kind === "profile") text += " " + _("Socle commun ajouté : ce vin a peu de molécules propres.");
    if (s.hidden_sources) text += " " + plural(_("%s élément naturel de plus dans les fiches."), _("%s éléments naturels de plus dans les fiches."), s.hidden_sources);
    stats.textContent = text;
  }

  // ── Vue d'un vin : phrase-titre, âge, « Voir tout », le reste du nez ─────
  const wineBar = document.getElementById("mol-wine-bar");
  const headlineEl = document.getElementById("mol-headline");
  const ageBox = document.getElementById("mol-age");
  const ageYears = document.getElementById("mol-age-years");
  const moreBtn = document.getElementById("mol-more");
  const restBox = document.getElementById("mol-rest");
  const restList = document.getElementById("mol-rest-list");
  function renderWine(data, kind) {
    const isWine = kind === "profile";
    const age = data.age || {};
    headlineEl.textContent = isWine ? data.headline || "" : "";
    ageBox.hidden = !(isWine && age.toggle);
    wineBar.hidden = !(isWine && (data.headline || age.toggle));
    printBtn.hidden = !isWine;
    if (isWine && age.age) state.age = age.age;
    ageBox.querySelectorAll("[data-age]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.age === age.age)));
    const [lo, hi] = age.aging || [];
    ageYears.textContent = lo != null && hi ? _("(%a à %b ans)").replace("%a", lo).replace("%b", hi) : "";
    const s = data.stats || {};
    moreBtn.hidden = !isWine || !(s.more || state.everything);
    moreBtn.textContent = state.everything ? _("Moins de molécules")
      : plural(_("Voir %s molécule de plus"), _("Voir %s molécules de plus"), s.more || 0);
    restList.innerHTML = "";
    (isWine ? data.unexplained || [] : []).forEach((u) => {
      const li = document.createElement("li");
      const tag = document.createElement("span");
      tag.className = "mol-rest__aroma";
      tag.style.setProperty("--c", u.hue || "");
      tag.textContent = u.label;
      const why = document.createElement("span");
      why.textContent = u.reason;
      li.append(tag, why);
      if (u.note) {
        const note = document.createElement("span");
        note.className = "mol-rest__note";
        note.textContent = u.note;
        li.appendChild(note);
      }
      restList.appendChild(li);
    });
    restBox.hidden = !restList.children.length;
  }
  ageBox.addEventListener("click", (e) => {
    const b = e.target.closest("[data-age]");
    if (!b || b.dataset.age === state.age) return;
    state.age = b.dataset.age;
    load(state.start, { push: false });
  });
  moreBtn.addEventListener("click", () => { state.everything = !state.everything; load(state.start, { push: false }); });

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
    else if (type === "source" || type === "aroma") {
      const twins = cy.nodes().filter((n) => (n.data("of") || n.id()) === (node.data("of") || node.id()));
      chain = twins.union(twins.predecessors());
    }
    cy.elements().addClass("faded").removeClass("hl");
    chain.removeClass("faded").addClass("hl");
  }
  function clearHighlight() { cy.elements().removeClass("faded hl"); }

  function openPanel(id) {
    const rootProfile = state.start.startsWith("profile:") ? state.start.split(":")[1] : "";
    let url = PANEL.replace("X", encodeURIComponent(id));
    if ((id.startsWith("molecule:") || id.startsWith("aroma:")) && rootProfile) url += `?vin=${encodeURIComponent(rootProfile)}`;
    if (window.htmx) htmx.ajax("GET", url, { target: "#mol-panel", swap: "innerHTML" });
  }

  // Une étiquette répétée (splitFarLabels) s'éclaire avec ses copies et ouvre la fiche de l'original.
  const realId = (n) => n.data("of") || n.id();
  cy.on("tap", "node", (e) => { highlight(e.target); openPanel(realId(e.target)); });
  // Un arôme n'est pas un point de départ : sa fiche, dans le panneau, mène à l'élément naturel.
  cy.on("dbltap", "node", (e) => { if (e.target.data("type") !== "aroma") load(realId(e.target)); });
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
  if (wikiBox) wikiBox.addEventListener("change", () => { state.wikidata = wikiBox.checked; if (state.start) load(state.start, { push: false }); });

  document.getElementById("mol-fit").addEventListener("click", () => layout());
  window.addEventListener("resize", () => { clearTimeout(window.__molResize); window.__molResize = setTimeout(layout, 200); });
  // ── Fiche imprimable (vue d'un vin) ──────────────────────────────────────
  // Le bouquet est redessiné hors écran dans un cadre d'ordinateur (960 px), même depuis un téléphone,
  // puis exporté en image nette (×3) ; le texte de la fiche (molécules, raisons, sources) vient du
  // serveur. La fiche remplace la page à l'impression (feuille de style « print »).
  const printBtn = document.getElementById("mol-print-btn");
  async function bouquetImage() {
    const canvas = cy.container().parentElement;
    clearHighlight();
    cy.$(":selected").unselect();
    cy.nodes().stop(true, true).removeStyle("opacity");
    printing = true;
    ownResize = Date.now();
    canvas.classList.add("is-printing");
    cy.resize();
    layout();
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    const png = cy.png({ full: true, scale: 3, bg: "#FFFFFF", maxWidth: 3200 });
    ownResize = Date.now();
    canvas.classList.remove("is-printing");
    printing = false;
    cy.resize();
    layout();
    return png;
  }
  async function printSheet() {
    if (!state.start.startsWith("profile:") || !PRINT) return;
    printBtn.disabled = true;
    try {
      const slug = state.start.split(":")[1];
      const url = `${PRINT.replace("X", encodeURIComponent(slug))}?${query().slice(1)}`;
      const [html, png] = await Promise.all([fetch(url).then((r) => { if (!r.ok) throw r; return r.text(); }), bouquetImage()]);
      let sheet = document.getElementById("mol-print-sheet");
      if (!sheet) {
        sheet = document.createElement("div");
        sheet.id = "mol-print-sheet";
        document.body.appendChild(sheet);
      }
      sheet.innerHTML = html;
      const img = sheet.querySelector("img[data-bouquet]");
      await new Promise((resolve) => { img.onload = resolve; img.onerror = resolve; img.src = png; });
      if (document.fonts && document.fonts.ready) await document.fonts.ready;
      document.body.classList.add("has-print-sheet");
      window.print();
    } catch (err) {
      stats.textContent = _("Impossible de préparer la fiche à imprimer.");
    } finally {
      printBtn.disabled = false;
    }
  }
  window.addEventListener("afterprint", () => document.body.classList.remove("has-print-sheet"));
  printBtn.addEventListener("click", printSheet);

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
      // Le bouquet règle lui-même la hauteur de son cadre : pas de nouvelle mise en page pour ça.
      if (Date.now() - ownResize < 600) return;
      clearTimeout(window.__molResize);
      window.__molResize = setTimeout(() => { cy.resize(); if (state.start) layout(); }, 120);
    }).observe(cy.container());
  }

  // ── Démarrage ──────────────────────────────────────────────────────────
  const params = new URLSearchParams(location.search);
  state.common = params.get("commun") === "1";
  commonBox.checked = state.common;
  state.wikidata = params.get("wikidata") !== "0";
  if (wikiBox) wikiBox.checked = state.wikidata;
  const first = params.get("depart") || root.dataset.start;
  // L'âge et « Voir tout » de l'adresse valent pour ce premier vin (load ne les remet à zéro qu'au changement).
  state.age = ["jeune", "mature"].includes(params.get("age")) ? params.get("age") : null;
  state.everything = params.get("tout") === "1";
  // « ?imprimer=1 » (lien « Fiche à imprimer » d'une fiche vin) : la fiche s'ouvre dès que le bouquet est prêt.
  if (first) {
    state.start = first;
    const ready = load(first);
    if (params.get("imprimer") === "1") {
      ready.then(() => (document.fonts && document.fonts.ready) || null).then(() => setTimeout(printSheet, 500));
    }
  }
  else stats.textContent = _("Choisissez un point de départ.");
})();
