/* Menus « Jeux » et « Explorer » de l'en-tête : s'ouvrent au clic ou au clavier, se ferment dehors ou avec Échap.
   Un seul ouvert à la fois. */
(function () {
  "use strict";
  document.querySelectorAll("[data-nav-group]").forEach((group) => {
    const toggle = group.querySelector(".nav-group__toggle");
    const set = (open) => {
      group.classList.toggle("is-open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    };
    toggle.addEventListener("click", () => {
      const open = !group.classList.contains("is-open");
      if (open) document.querySelectorAll("[data-nav-group].is-open").forEach((g) => g !== group && g.querySelector(".nav-group__toggle").click());
      set(open);
    });
    document.addEventListener("click", (e) => { if (!group.contains(e.target)) set(false); });
    group.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { set(false); toggle.focus(); }
    });
    group.addEventListener("focusout", (e) => { if (!group.contains(e.relatedTarget)) set(false); });
  });
})();
