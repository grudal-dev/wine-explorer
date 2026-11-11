/* Chaud-froid : autocomplétion des propositions, rechargée après chaque essai HTMX. */
(function () {
  "use strict";

  function init() {
    const board = document.getElementById("hotcold");
    const input = document.getElementById("hotcold-input");
    if (!board || !input || input.dataset.ready) return;
    input.dataset.ready = "1";
    const form = input.closest("form");
    const choice = form.querySelector("input[name='choice']");
    const url = board.dataset.search;

    input.addEventListener("input", () => { choice.value = ""; });
    Combo.attach(input, {
      source: async (q) => (await Combo.getJSON(`${url}?q=${encodeURIComponent(q)}`)).results
        .map((r) => ({ ...r, hint: r.type_label })),
      onSelect: (it) => {
        input.value = it.label;
        choice.value = it.id;
        form.requestSubmit();
      },
      onEnter: () => form.requestSubmit(),
    });
    input.focus();
  }

  document.addEventListener("DOMContentLoaded", init);
  document.body.addEventListener("htmx:afterSwap", init);
})();
