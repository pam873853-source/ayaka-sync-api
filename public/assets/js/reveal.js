/* ==========================================================================
   Scroll reveal — elements animate in every time they enter the viewport,
   in both scroll directions:
     • scrolling down  → element rises in from below
     • scrolling up    → element drops in from above
   When an element fully leaves the viewport it is reset, so the animation
   plays again the next time it comes back. Respects prefers-reduced-motion
   and the user's "Scroll animations" switch (Settings → Appearance), which is
   a non-sensitive UI preference stored in localStorage (`ayaka.motion`).
   ========================================================================== */
(function () {
  "use strict";
  var MOTION_KEY = "ayaka.motion";
  var supported = "IntersectionObserver" in window;
  var reduce = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;

  function userEnabled() {
    try { return localStorage.getItem(MOTION_KEY) !== "off"; } catch (e) { return true; }
  }
  function systemReduced() { return !!(reduce && reduce.matches); }

  var SELECTORS = [
    // marketing / public pages
    ".hero .container > div:first-child > *", ".hero .terminal",
    ".section-head > *", ".feature > *", ".step", ".cta-inner",
    ".footer-grid > div", ".footer-bottom",
    ".docs-content > section > *",
    ".status-hero > *", ".status-row",
    ".legal > *",
    // authenticated app
    ".page-head", ".page .card", ".page > .callout", ".quick-action",
  ].join(",");

  var STATE = "data-reveal";
  var IN_RATIO = 0.12;     // share of the element that must be visible to reveal it
  var IN_PX = 72;          // …or this many pixels (for elements taller than the viewport)
  var STAGGER_MS = 70;
  var MAX_STAGGER = 6;

  function viewportH() { return window.innerHeight || document.documentElement.clientHeight; }

  function isRendered(el) {
    var r = el.getBoundingClientRect();
    return r.width > 0 || r.height > 0;
  }

  // Initial state, computed synchronously so content already on screen never flickers.
  function initialState(el) {
    if (!isRendered(el)) return "shown";
    var r = el.getBoundingClientRect();
    if (r.top >= viewportH()) return "below";
    if (r.bottom <= 0) return "above";
    return "shown";
  }

  var io = null;
  var mo = null;
  var tracked = new WeakSet();
  var running = false;

  function onIntersect(entries) {
    var entering = [];
    entries.forEach(function (e) {
      var el = e.target;
      var st = el.getAttribute(STATE);
      if (!e.isIntersecting) {
        // Fully out of view: park it on the side it left from so it can animate back in.
        if (!isRendered(el)) return;
        var side = e.boundingClientRect.top > 0 ? "below" : "above";
        if (st !== side) el.setAttribute(STATE, side);
        return;
      }
      if (st !== "below" && st !== "above") return;
      var visible = e.intersectionRatio >= IN_RATIO || e.intersectionRect.height >= IN_PX;
      if (visible) entering.push({ el: e.target, from: st, top: e.boundingClientRect.top, left: e.boundingClientRect.left });
    });
    if (!entering.length) return;
    // Stagger siblings that enter together, in reading order for the scroll direction.
    entering.sort(function (a, b) {
      var dir = a.from === "above" ? -1 : 1;
      return (a.top - b.top) * dir || a.left - b.left;
    });
    entering.forEach(function (item, i) {
      item.el.style.setProperty("--reveal-delay", Math.min(i, MAX_STAGGER) * STAGGER_MS + "ms");
      item.el.setAttribute(STATE, item.from === "below" ? "in-up" : "in-down");
    });
  }

  function scan(root) {
    var nodes = (root || document).querySelectorAll(SELECTORS);
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      if (tracked.has(el)) continue;
      // Never nest reveals (a revealed card's children move with it).
      if (el.parentElement && el.parentElement.closest("[" + STATE + "]")) continue;
      if (el.closest(".modal-root, .dropdown-menu, .sidebar, .topbar, .site-nav, .docs-nav, .toast-stack")) continue;
      tracked.add(el);
      el.setAttribute(STATE, initialState(el));
      io.observe(el);
    }
  }

  function start() {
    if (running || !supported || systemReduced() || !userEnabled()) return;
    running = true;
    tracked = new WeakSet();
    io = new IntersectionObserver(onIntersect, { threshold: [0, 0.05, IN_RATIO, 0.25, 0.5, 1] });
    scan();
    // Cards rendered later by page scripts.
    var pending = false;
    mo = new MutationObserver(function () {
      if (pending || !running) return;
      pending = true;
      requestAnimationFrame(function () { pending = false; if (running) scan(); });
    });
    mo.observe(document.body, { childList: true, subtree: true });
  }

  function stop() {
    if (!running) return;
    running = false;
    if (io) io.disconnect();
    if (mo) mo.disconnect();
    io = mo = null;
    // Show everything immediately, without animating.
    var nodes = document.querySelectorAll("[" + STATE + "]");
    for (var i = 0; i < nodes.length; i++) {
      nodes[i].removeAttribute(STATE);
      nodes[i].style.removeProperty("--reveal-delay");
    }
  }

  function applyRootClass() {
    document.documentElement.classList.toggle("no-scroll-anim", !userEnabled());
  }

  function syncControls() {
    var on = userEnabled();
    var inputs = document.querySelectorAll("[data-motion-toggle]");
    for (var i = 0; i < inputs.length; i++) inputs[i].checked = on;
    var notes = document.querySelectorAll("[data-motion-system-note]");
    for (var j = 0; j < notes.length; j++) notes[j].classList.toggle("hidden", !systemReduced());
  }

  function setEnabled(on) {
    try { localStorage.setItem(MOTION_KEY, on ? "on" : "off"); } catch (e) { /* applies to this page only */ }
    applyRootClass();
    if (on) start(); else stop();
    syncControls();
    window.dispatchEvent(new CustomEvent("motionchange", { detail: { enabled: on, systemReduced: systemReduced() } }));
  }

  applyRootClass();

  document.addEventListener("change", function (e) {
    if (e.target && e.target.matches && e.target.matches("[data-motion-toggle]")) setEnabled(e.target.checked);
  });

  // Another tab flipped the switch.
  window.addEventListener("storage", function (e) {
    if (e.key !== MOTION_KEY) return;
    applyRootClass();
    if (userEnabled()) start(); else stop();
    syncControls();
  });

  if (reduce) {
    var onReduce = function () { if (systemReduced()) stop(); else start(); syncControls(); };
    if (reduce.addEventListener) reduce.addEventListener("change", onReduce); else if (reduce.addListener) reduce.addListener(onReduce);
  }

  function boot() { syncControls(); start(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();

  window.AyakaReveal = {
    get enabled() { return userEnabled(); },
    get active() { return running; },
    setEnabled: setEnabled,
    sync: syncControls,
  };
})();
