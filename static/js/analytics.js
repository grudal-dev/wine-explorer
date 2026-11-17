// Mesure d'audience : temps réellement passé sur la page (onglet visible) et défilement maximal.
// Aucun cookie, aucun identifiant côté navigateur ; envoyé une fois en quittant la page.
(function () {
  "use strict";
  var endpoint = document.currentScript && document.currentScript.dataset.endpoint;
  if (!endpoint || !navigator.sendBeacon) return;
  if (navigator.doNotTrack === "1" || navigator.globalPrivacyControl) return;

  var visibleSince = document.visibilityState === "visible" ? Date.now() : null;
  var total = 0;
  var maxScroll = 0;
  var sent = false;

  function scrollPct() {
    var doc = document.documentElement;
    var height = doc.scrollHeight - window.innerHeight;
    return height <= 0 ? 100 : Math.round(100 * Math.min(1, window.scrollY / height));
  }

  function pause() {
    if (visibleSince !== null) { total += Date.now() - visibleSince; visibleSince = null; }
  }

  function send() {
    pause();
    if (sent || total < 1000) return;
    sent = true;
    var body = JSON.stringify({ p: location.pathname, t: total, s: maxScroll });
    navigator.sendBeacon(endpoint, new Blob([body], { type: "application/json" }));
  }

  window.addEventListener("scroll", function () { maxScroll = Math.max(maxScroll, scrollPct()); }, { passive: true });
  window.addEventListener("load", function () { maxScroll = Math.max(maxScroll, scrollPct()); });
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") { send(); }
    else { visibleSince = Date.now(); sent = false; }
  });
  window.addEventListener("pagehide", send);
})();
