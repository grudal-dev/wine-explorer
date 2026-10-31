/* Le Nez : sélection de descripteurs en puces, recalcul HTMX à chaque changement. */
(function () {
  "use strict";

  const root = document.getElementById("nose");
  if (!root) return;
  const form = document.getElementById("nose-form");
  const chips = document.getElementById("chips");
  const empty = form.querySelector(".chips-empty");
  const input = document.getElementById("aroma-input");
  const api = root.dataset.api;

  function has(kind, id) {
    return !!chips.querySelector(`input[name='${kind}'][value='${id}']`);
  }

  function refresh() {
    input.value = "";
    empty.hidden = chips.children.length > 0;
    syncWheel();
    form.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function addChip(kind, id, label, hue, axis) {
    if (has(kind, id)) return;
    if (kind === "s" && axis) {
      // Un seul descripteur par axe de la bouche : le nouveau remplace l'ancien.
      chips.querySelectorAll(`.chip--sense[data-axis='${axis}']`).forEach((c) => c.remove());
    }
    const span = document.createElement("span");
    span.className = "chip" + (kind === "f" ? " chip--family" : "") + (kind === "s" ? " chip--sense" : "");
    if (axis) span.dataset.axis = axis;
    span.style.setProperty("--hue", hue || "#888");
    const hidden = document.createElement("input");
    hidden.type = "hidden"; hidden.name = kind; hidden.value = id;
    const x = document.createElement("button");
    x.type = "button"; x.className = "chip__x"; x.textContent = "×";
    x.setAttribute("aria-label", `Retirer ${label}`);
    span.append(hidden, document.createTextNode(label), x);
    chips.appendChild(span);
    refresh();
  }

  function syncWheel() {
    form.querySelectorAll("[data-add-aroma]").forEach((b) => {
      b.setAttribute("aria-pressed", has("a", b.dataset.addAroma) ? "true" : "false");
    });
    form.querySelectorAll("[data-add-family]").forEach((b) => {
      b.setAttribute("aria-pressed", has("f", b.dataset.addFamily) ? "true" : "false");
    });
    form.querySelectorAll("[data-add-sense]").forEach((b) => {
      b.setAttribute("aria-pressed", has("s", b.dataset.addSense) ? "true" : "false");
    });
  }

  chips.addEventListener("click", (e) => {
    const x = e.target.closest(".chip__x");
    if (!x) return;
    x.parentElement.remove();
    refresh();
  });

  form.addEventListener("click", (e) => {
    const a = e.target.closest("[data-add-aroma]");
    const f = e.target.closest("[data-add-family]");
    const sn = e.target.closest("[data-add-sense]");
    if (a) toggle("a", a.dataset.addAroma, a.dataset.label, a.dataset.hue);
    else if (f) toggle("f", f.dataset.addFamily, f.dataset.label, f.dataset.hue);
    else if (sn) toggle("s", sn.dataset.addSense, sn.dataset.label, "", sn.dataset.axis);
  });

  function toggle(kind, id, label, hue, axis) {
    if (has(kind, id)) {
      chips.querySelector(`input[name='${kind}'][value='${id}']`).parentElement.remove();
      refresh();
    } else {
      addChip(kind, id, label, hue, axis);
    }
  }

  // Suggestions « pour confirmer » dans les résultats
  document.getElementById("results").addEventListener("click", (e) => {
    const b = e.target.closest("[data-suggest-aroma]");
    if (!b) return;
    const btn = form.querySelector(`[data-add-aroma][data-label="${CSS.escape(b.dataset.suggestAroma)}"]`);
    if (btn) addChip("a", btn.dataset.addAroma, btn.dataset.label, btn.dataset.hue);
  });

  document.getElementById("nose-reset").addEventListener("click", () => {
    chips.innerHTML = "";
    form.querySelectorAll("input[name='c']").forEach((c) => { c.checked = false; });
    refresh();
  });

  // Le champ texte ne doit pas déclencher de recherche à chaque frappe
  input.addEventListener("change", (e) => e.stopPropagation());

  Combo.attach(input, {
    source: async (q) => (await Combo.getJSON(`${api}?q=${encodeURIComponent(q)}`)).results
      .map((r) => ({ ...r, hint: r.kind_label })),
    onSelect: (it) => {
      if (it.kind === "sense") { addChip("s", it.pk, it.label, "", it.axis); return; }
      const btn = form.querySelector(it.kind === "family" ? `[data-add-family='${it.pk}']` : `[data-add-aroma='${it.pk}']`);
      addChip(it.kind === "family" ? "f" : "a", it.pk, it.label, btn ? btn.dataset.hue : "#888");
    },
    onEnter: () => {},
  });

  syncWheel();
})();
