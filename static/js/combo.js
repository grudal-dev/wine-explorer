/* Combobox accessible et minimaliste, partagé par le graphe, le blind test et Le Nez.
 *
 *   Combo.attach(input, {
 *     source: (q) => Promise<[{label, hint, ...}]>,
 *     onSelect: (item) => {},
 *     onEnter: (text) => {},   // Entrée sans suggestion sélectionnée (optionnel)
 *   })
 */
(function () {
  "use strict";

  function debounce(fn, ms) {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
  }

  function attach(input, opts) {
    const list = document.getElementById(input.getAttribute("aria-controls"));
    let items = [];
    let active = -1;
    let seq = 0;

    function close() {
      list.hidden = true;
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
      active = -1;
    }

    function render() {
      list.innerHTML = "";
      items.forEach((it, i) => {
        const li = document.createElement("li");
        li.id = `${list.id}-${i}`;
        li.setAttribute("role", "option");
        li.className = "combo__item" + (i === active ? " is-active" : "");
        li.setAttribute("aria-selected", i === active ? "true" : "false");
        const label = document.createElement("span");
        label.textContent = it.label;
        li.appendChild(label);
        if (it.hint) {
          const hint = document.createElement("span");
          hint.className = "combo__hint";
          hint.textContent = it.hint;
          li.appendChild(hint);
        }
        li.addEventListener("mousedown", (e) => { e.preventDefault(); choose(i); });
        list.appendChild(li);
      });
      const open = items.length > 0;
      list.hidden = !open;
      input.setAttribute("aria-expanded", open ? "true" : "false");
      if (active >= 0) input.setAttribute("aria-activedescendant", `${list.id}-${active}`);
    }

    function choose(i) {
      const it = items[i];
      close();
      if (it) opts.onSelect(it);
    }

    const query = debounce(async () => {
      const q = input.value.trim();
      const mine = ++seq;
      if (q.length < 2) { items = []; close(); return; }
      try {
        const res = await opts.source(q);
        if (mine !== seq) return;
        items = res;
        active = items.length ? 0 : -1;
        render();
      } catch (err) {
        console.error(err);
      }
    }, 140);

    input.addEventListener("input", query);
    input.addEventListener("blur", () => setTimeout(close, 100));
    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown" && items.length) {
        e.preventDefault(); active = (active + 1) % items.length; render();
      } else if (e.key === "ArrowUp" && items.length) {
        e.preventDefault(); active = (active - 1 + items.length) % items.length; render();
      } else if (e.key === "Enter") {
        if (!list.hidden && active >= 0) { e.preventDefault(); choose(active); }
        else if (opts.onEnter) { e.preventDefault(); opts.onEnter(input.value.trim()); }
      } else if (e.key === "Escape") {
        close();
      }
    });
    return { close, clear: () => { input.value = ""; items = []; close(); } };
  }

  async function getJSON(url) {
    const res = await fetch(url, { headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  window.Combo = { attach, getJSON };
})();
