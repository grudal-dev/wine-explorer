/* Comparer : chaque vin se choisit en tapant son nom, son appellation, sa région ou un cépage.
   Choisir une suggestion ouvre aussitôt le duel. */
(function () {
  "use strict";

  function init() {
    const form = document.getElementById("duel-pick");
    if (!form) return;
    const url = form.dataset.search;
    form.querySelectorAll(".duel-pick__input").forEach((input) => {
      const hidden = form.querySelector(`input[name='${input.dataset.slot}']`);
      const initial = input.value;
      input.addEventListener("focus", () => input.select());
      input.addEventListener("blur", () => setTimeout(() => {
        if (!input.value.trim()) input.value = initial;   // rien choisi : on remet le vin en cours
      }, 150));
      Combo.attach(input, {
        source: async (q) => (await Combo.getJSON(`${url}?q=${encodeURIComponent(q)}`)).results,
        onSelect: (it) => {
          input.value = it.label;
          hidden.value = it.slug;
          const a = form.querySelector("input[name='a']").value;
          const b = form.querySelector("input[name='b']").value;
          if (a && b) window.location.href = `${form.action.replace(/\/$/, "")}/${a}/${b}/`;
        },
      });
    });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
