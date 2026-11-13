/* Menu « Jeux » de l'en-tête : s'ouvre au clic ou au clavier, se ferme dehors ou avec Échap. */
(function () {
  "use strict";
  document.querySelectorAll("[data-nav-group]").forEach((group) => {
    const toggle = group.querySelector(".nav-group__toggle");
    const set = (open) => {
      group.classList.toggle("is-open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    };
    toggle.addEventListener("click", () => set(!group.classList.contains("is-open")));
    document.addEventListener("click", (e) => { if (!group.contains(e.target)) set(false); });
    group.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { set(false); toggle.focus(); }
    });
    group.addEventListener("focusout", (e) => { if (!group.contains(e.relatedTarget)) set(false); });
  });
})();
