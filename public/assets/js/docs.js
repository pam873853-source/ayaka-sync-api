/* Documentation page: base URL, code tabs, scrollspy and the Try-endpoint panel. */
import "./site.js";
import { API_BASE } from "./api.js";
import { $, $$, bindPasswordToggles, copyText, esc, toast } from "./components.js";

bindPasswordToggles();

// ---- base URL: the domain this page is served from (Vercel URL, alias or custom domain).
// An explicit APP_BASE_URL on the server wins, unless it still points at localhost while the
// page is served from a real domain (a common copy-paste mistake from .env.example).
const isLoopback = (u) => { try { const h = new URL(u).hostname; return h === "localhost" || h === "127.0.0.1" || h === "0.0.0.0" || h === "[::1]" || h.endsWith(".localhost"); } catch { return false; } };
const absoluteBase = new URL(API_BASE || "/api/v1", window.location.origin).href.replace(/\/$/, "");
const setBase = (base) => $$("[data-api-base]").forEach((el) => { el.textContent = base; });
setBase(absoluteBase);
fetch(`${API_BASE}/meta`, { credentials: "same-origin" })
  .then((r) => (r.ok ? r.json() : null))
  .then((body) => {
    const d = body?.data;
    if (!d) return;
    const serverBase = (d.api_base || "").replace(/\/$/, "");
    const useServer = serverBase && d.base_url_source === "env" && !(isLoopback(serverBase) && !isLoopback(absoluteBase));
    setBase(useServer ? serverBase : absoluteBase);
    if (d.rate_limit_default) $$("[data-rate-default]").forEach((el) => { el.textContent = String(d.rate_limit_default); });
  })
  .catch(() => {});

// ---- code tabs
$$("[data-tabs]").forEach((box) => {
  box.addEventListener("click", async (e) => {
    const tab = e.target.closest("[data-tab]");
    if (tab) {
      $$("[data-tab]", box).forEach((b) => b.classList.toggle("is-active", b === tab));
      $$("[data-pane]", box).forEach((p) => p.classList.toggle("hidden", p.dataset.pane !== tab.dataset.tab));
      return;
    }
    if (e.target.closest("[data-copy-active]")) {
      const pane = $$("[data-pane]", box).find((p) => !p.classList.contains("hidden"));
      if (pane && await copyText(pane.textContent.trim())) toast.success("Code copied");
    }
  });
});

// ---- scrollspy
const links = $$("#docs-nav a[href^='#']");
const sections = links.map((a) => document.getElementById(a.getAttribute("href").slice(1))).filter(Boolean);
const spy = new IntersectionObserver((entries) => {
  const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
  if (!visible) return;
  links.forEach((a) => a.classList.toggle("is-active", a.getAttribute("href") === `#${visible.target.id}`));
}, { rootMargin: "-80px 0px -65% 0px" });
sections.forEach((s) => spy.observe(s));

// ---- try endpoint (GET only, key kept in memory)
const sel = $("#try-endpoint");
const keyInput = $("#try-key");
const keyField = $("#try-key-field");
const sendBtn = $("#try-send");
const out = $("#try-output");
const outWrap = $("#try-output-wrap");
const status = $("#try-status");
const meta = $("#try-meta");

function syncKeyField() {
  const needsKey = sel.selectedOptions[0]?.dataset.auth === "1";
  keyField.classList.toggle("hidden", !needsKey);
}
sel?.addEventListener("change", syncKeyField);
syncKeyField();

sendBtn?.addEventListener("click", async () => {
  const path = sel.value;
  const needsKey = sel.selectedOptions[0]?.dataset.auth === "1";
  const key = keyInput.value.trim();
  if (needsKey && !key) {
    toast.error("API key required", "Paste an API key to call this endpoint.");
    keyInput.focus();
    return;
  }
  if (needsKey && !/^ayk_(live|test)_[A-Za-z0-9_-]+$/.test(key)) {
    toast.error("Invalid key format", "Ayaka keys start with ayk_live_ or ayk_test_.");
    return;
  }
  sendBtn.disabled = true;
  meta.textContent = "Sending…";
  const started = performance.now();
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method: "GET",
      credentials: "omit", // never send the dashboard session — only the key
      headers: needsKey ? { Authorization: `Bearer ${key}` } : {},
    });
    const ms = Math.round(performance.now() - started);
    let text = await res.text();
    try { text = JSON.stringify(JSON.parse(text), null, 2); } catch { /* keep raw */ }
    const hdrs = ["x-request-id", "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset", "retry-after"]
      .filter((h) => res.headers.get(h) !== null)
      .map((h) => `${h}: ${res.headers.get(h)}`);
    status.innerHTML = `<span class="${res.ok ? "text-success" : "text-danger"}">HTTP ${res.status}</span> · GET ${esc(path)}`;
    out.textContent = (hdrs.length ? hdrs.join("\n") + "\n\n" : "") + text;
    outWrap.classList.remove("hidden");
    meta.textContent = `${ms} ms`;
  } catch {
    meta.textContent = "";
    toast.error("Connection problem", "Could not reach the API.");
  } finally {
    sendBtn.disabled = false;
  }
});
