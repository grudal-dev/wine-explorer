/* Fin de partie : partager le résultat sans dévoiler le vin. Texte (grille de pastilles + lien), image du
   score dessinée à la volée, lien de défi. Délégation sur le document : le plateau est remplacé par htmx. */
(function () {
  "use strict";
  const _ = window.gettext || ((s) => s);

  function flash(box) {
    const done = box.querySelector("[data-share-done]");
    if (!done) return;
    done.hidden = false;
    clearTimeout(done._t);
    done._t = setTimeout(() => { done.hidden = true; }, 3500);
  }

  async function copy(text) {
    try { await navigator.clipboard.writeText(text); return true; } catch (e) { /* repli ci-dessous */ }
    const ta = document.createElement("textarea");
    ta.value = text; ta.setAttribute("readonly", ""); ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta); ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    ta.remove();
    return ok;
  }

  async function shareText(box, text) {
    // Téléphone : la feuille de partage du système ; ordinateur : le presse-papiers.
    if (navigator.share && matchMedia("(pointer: coarse)").matches) {
      try { await navigator.share({ text }); return; } catch (e) { if (e && e.name === "AbortError") return; }
    }
    if (await copy(text)) flash(box);
  }

  // Image 1080 × 1080 : nom du site, numéro du défi, grille, score. Rien qui trahisse le vin.
  function drawImage(box) {
    const c = document.createElement("canvas");
    c.width = 1080; c.height = 1080;
    const g = c.getContext("2d");
    const grid = [...(box.dataset.grid || "")].filter((ch) => ch.trim());
    g.fillStyle = "#F4F1EA"; g.fillRect(0, 0, 1080, 1080);
    g.fillStyle = "#6E1A33"; g.beginPath(); g.arc(540, 250, 70, 0, Math.PI * 2); g.fill();
    g.fillStyle = "#23262F"; g.textAlign = "center";
    g.font = "600 64px Fraunces, Georgia, serif";
    g.fillText(box.dataset.name || "", 540, 420);
    g.font = "500 40px Inter, system-ui, sans-serif"; g.fillStyle = "#5B5E68";
    const num = box.dataset.number ? _("Vin du jour n° %s").replace("%s", box.dataset.number) : _("Blind test");
    g.fillText(num, 540, 490);
    const colours = { "🟩": "#6B8E3D", "🟨": "#D6A93A", "🟥": "#B4463C", "⬜": "#D9D4CA" };
    const size = 84, gap = 18, n = grid.length || 1;
    const x0 = 540 - (n * size + (n - 1) * gap) / 2;
    grid.forEach((ch, i) => {
      g.fillStyle = colours[ch] || "#D9D4CA";
      const x = x0 + i * (size + gap);
      if (g.roundRect) { g.beginPath(); g.roundRect(x, 580, size, size, 14); g.fill(); } else g.fillRect(x, 580, size, size);
    });
    g.fillStyle = "#23262F"; g.font = "600 120px Fraunces, Georgia, serif";
    g.fillText(box.dataset.score || "", 540, 830);
    g.font = "500 34px Inter, system-ui, sans-serif"; g.fillStyle = "#5B5E68";
    g.fillText((box.dataset.url || "").replace(/^https?:\/\//, "").replace(/\/$/, ""), 540, 960);
    return new Promise((resolve) => c.toBlob(resolve, "image/png"));
  }

  async function shareImage(box) {
    const blob = await drawImage(box);
    if (!blob) return;
    const file = new File([blob], "score.png", { type: "image/png" });
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      try { await navigator.share({ files: [file], text: box.querySelector("[data-share-text]").value }); return; }
      catch (e) { if (e && e.name === "AbortError") return; }
    }
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "score.png";
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }

  document.addEventListener("click", (ev) => {
    const box = ev.target.closest("[data-share]");
    if (!box) return;
    if (ev.target.closest("[data-share-button]")) {
      shareText(box, box.querySelector("[data-share-text]").value);
    } else if (ev.target.closest("[data-share-image]")) {
      shareImage(box);
    } else if (ev.target.closest("[data-share-challenge]")) {
      const btn = ev.target.closest("[data-share-challenge]");
      shareText(box, `${btn.dataset.text} ${box.dataset.url}`);
    }
  });
})();
