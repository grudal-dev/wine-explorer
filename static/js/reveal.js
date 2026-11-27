/* Bouton « Afficher » à côté d'un mot de passe : on le vérifie d'un coup d'œil au lieu de le taper deux fois. */
(function () {
  "use strict";
  const _ = window.gettext || ((s) => s);
  document.querySelectorAll("input[data-reveal]").forEach((input) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "reveal";
    btn.textContent = _("Afficher");
    btn.setAttribute("aria-pressed", "false");
    btn.addEventListener("click", () => {
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.textContent = show ? _("Masquer") : _("Afficher");
      btn.setAttribute("aria-pressed", String(show));
    });
    const wrap = document.createElement("div");
    wrap.className = "reveal-wrap";
    input.parentNode.insertBefore(wrap, input);
    wrap.append(input, btn);
  });
})();
