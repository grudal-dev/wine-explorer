/* Compte à rebours jusqu'au prochain défi : met à jour tout élément [data-deadline]. */
(function () {
  "use strict";
  const clocks = document.querySelectorAll("[data-deadline]");
  if (!clocks.length) return;
  const pad = (n) => String(n).padStart(2, "0");
  function tick() {
    const now = Date.now();
    clocks.forEach((el) => {
      const left = Math.max(0, Math.floor((new Date(el.dataset.deadline).getTime() - now) / 1000));
      el.textContent = `${pad(Math.floor(left / 3600))}:${pad(Math.floor((left % 3600) / 60))}:${pad(left % 60)}`;
    });
  }
  tick();
  setInterval(tick, 1000);
})();
