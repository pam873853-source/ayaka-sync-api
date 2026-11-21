/* ==========================================================================
   Theme (dark / light / system). Loaded synchronously in <head> so the
   correct theme is applied before first paint (no flash).
   The preference is a non-sensitive UI setting kept in localStorage.
   ========================================================================== */
(function () {
  "use strict";
  var KEY = "ayaka.theme";
  var MODES = ["dark", "light", "system"];
  var META = { dark: "#080808", light: "#fafafa" };
  var root = document.documentElement;
  var mq = window.matchMedia ? window.matchMedia("(prefers-color-scheme: light)") : null;

  function read() {
    try { var v = localStorage.getItem(KEY); return MODES.indexOf(v) >= 0 ? v : "dark"; } catch (e) { return "dark"; }
  }
  function resolve(mode) { return mode === "system" ? (mq && mq.matches ? "light" : "dark") : mode; }

  function apply(mode, silent) {
    var resolved = resolve(mode);
    var changed = root.getAttribute("data-theme") !== resolved;
    root.setAttribute("data-theme", resolved);
    root.setAttribute("data-theme-mode", mode);
    root.style.colorScheme = resolved;
    var metas = document.querySelectorAll('meta[name="theme-color"]');
    for (var i = 0; i < metas.length; i++) metas[i].setAttribute("content", META[resolved]);
    var cs = document.querySelector('meta[name="color-scheme"]');
    if (cs) cs.setAttribute("content", resolved);
    syncControls(mode, resolved);
    if (changed && !silent) {
      window.dispatchEvent(new CustomEvent("themechange", { detail: { mode: mode, theme: resolved } }));
    }
  }

  function syncControls(mode, resolved) {
    var toggles = document.querySelectorAll("[data-theme-toggle]");
    for (var i = 0; i < toggles.length; i++) {
      var label = resolved === "dark" ? "Switch to light mode" : "Switch to dark mode";
      toggles[i].setAttribute("aria-label", label);
      toggles[i].setAttribute("title", label);
    }
    var opts = document.querySelectorAll("[data-theme-option]");
    for (var j = 0; j < opts.length; j++) {
      var on = opts[j].getAttribute("data-theme-option") === mode;
      opts[j].classList.toggle("is-active", on);
      opts[j].setAttribute("aria-pressed", on ? "true" : "false");
    }
  }

  function set(mode) {
    if (MODES.indexOf(mode) < 0) return;
    try { localStorage.setItem(KEY, mode); } catch (e) { /* private mode: apply for this page only */ }
    root.classList.add("theme-switching");
    apply(mode);
    window.setTimeout(function () { root.classList.remove("theme-switching"); }, 250);
  }

  apply(read(), true);

  // Scroll-animation preference must be known before first paint so the hero
  // entrance animation does not start when the user has switched it off.
  try { if (localStorage.getItem("ayaka.motion") === "off") root.classList.add("no-scroll-anim"); } catch (e) { /* ignore */ }

  if (mq) {
    var onSystem = function () { if (read() === "system") apply("system"); };
    if (mq.addEventListener) mq.addEventListener("change", onSystem); else if (mq.addListener) mq.addListener(onSystem);
  }

  // Another tab changed the theme.
  window.addEventListener("storage", function (e) { if (e.key === KEY) apply(read()); });

  // Delegated handlers: toggles and options may be rendered later by JS.
  document.addEventListener("click", function (e) {
    var t = e.target.closest && e.target.closest("[data-theme-toggle]");
    if (t) { e.preventDefault(); set(resolve(read()) === "dark" ? "light" : "dark"); return; }
    var o = e.target.closest && e.target.closest("[data-theme-option]");
    if (o) { e.preventDefault(); set(o.getAttribute("data-theme-option")); }
  });

  document.addEventListener("DOMContentLoaded", function () { syncControls(read(), resolve(read())); });

  window.AyakaTheme = {
    get mode() { return read(); },
    get theme() { return resolve(read()); },
    set: set,
    sync: function () { syncControls(read(), resolve(read())); },
  };
})();
