/* ==========================================================================
   Authenticated app shell: session guard, sidebar, topbar, notifications.
   ========================================================================== */
import { api, API_ROOT, loadSession } from "./api.js";
import {
  $, $$, esc, fmtRelative, icon, initDropdowns, initTooltips, initials, logo, setPrefs, toast, toastError,
  bindCopyButtons, bindPasswordToggles, hydrateIcons,
} from "./components.js";

const NAV = [
  { id: "dashboard", label: "Overview", href: "dashboard.html", ic: "dashboard" },
  { id: "keys", label: "API Keys", href: "keys.html", ic: "key" },
  { id: "analytics", label: "Analytics", href: "analytics.html", ic: "chart" },
  { id: "docs", label: "Documentation", href: "docs.html", ic: "book" },
  { id: "activity", label: "Activity Logs", href: "activity.html", ic: "logs" },
  { id: "settings", label: "Settings", href: "settings.html", ic: "settings" },
];
const COLLAPSE_KEY = "ayaka.sidebar.collapsed"; // UI preference only, not sensitive

export const session = { user: null, settings: null };

function navLink(item, active) {
  return `<a class="nav-link ${active ? "is-active" : ""}" href="${item.href}" ${active ? 'aria-current="page"' : ""} data-nav-tip="${esc(item.label)}">
    ${icon(item.ic)}<span class="nav-text">${esc(item.label)}</span>${item.extra || ""}</a>`;
}

function renderSidebar(page) {
  const el = $("#sidebar");
  el.innerHTML = `
    <div class="sidebar-head">
      ${logo({ href: "dashboard.html" })}
      <button class="btn btn-ghost btn-sm btn-icon sidebar-collapse" id="collapse-btn" aria-label="Collapse sidebar">${icon("panel")}</button>
    </div>
    <nav class="sidebar-nav" aria-label="Main">
      <div class="sidebar-label">Workspace</div>
      ${NAV.map((n) => navLink(n, n.id === page)).join("")}
    </nav>
    <div class="sidebar-foot">
      ${navLink({ label: "Help Center", href: "docs.html#support", ic: "help" }, false)}
      ${navLink({ label: "API Status", href: "status.html", ic: "signal", extra: '<span class="status-dot" id="status-dot" title="Checking…"></span>' }, page === "status")}
      ${navLink({ id: "profile", label: "Profile", href: "profile.html", ic: "user" }, page === "profile")}
      <button class="nav-link" id="sidebar-logout" type="button">${icon("logout")}<span class="nav-text">Logout</span></button>
    </div>`;
  const app = $("#app");
  if (localStorage.getItem(COLLAPSE_KEY) === "1") app.classList.add("is-collapsed");
  const applyTips = () => {
    $$(".sidebar .nav-link").forEach((a) => {
      const label = a.dataset.navTip || a.textContent.trim();
      if (app.classList.contains("is-collapsed") && window.innerWidth > 900) a.dataset.tooltip = label;
      else delete a.dataset.tooltip;
    });
  };
  applyTips();
  $("#collapse-btn").addEventListener("click", () => {
    app.classList.toggle("is-collapsed");
    localStorage.setItem(COLLAPSE_KEY, app.classList.contains("is-collapsed") ? "1" : "0");
    applyTips();
    window.dispatchEvent(new Event("resize")); // let charts reflow
  });
  window.addEventListener("resize", applyTips);
  $("#sidebar-logout").addEventListener("click", logout);
}

function renderTopbar(crumbs) {
  const u = session.user;
  const name = session.settings?.display_name || u.username;
  const el = $("#topbar");
  el.innerHTML = `
    <button class="btn btn-ghost btn-icon topbar-toggle" id="drawer-btn" aria-label="Open menu" aria-controls="sidebar">${icon("menu")}</button>
    <nav class="breadcrumb" aria-label="Breadcrumb">
      <a href="dashboard.html">Dashboard</a>
      ${crumbs.map((c, i) => `<span class="sep">/</span>${i === crumbs.length - 1 ? `<span class="current">${esc(c.label)}</span>` : `<a href="${c.href}">${esc(c.label)}</a>`}`).join("")}
    </nav>
    <form class="topbar-search input-icon" id="global-search" role="search">
      ${icon("search")}
      <input class="input" type="search" name="q" placeholder="Search API keys…" aria-label="Search API keys" autocomplete="off">
      <span class="kbd">/</span>
    </form>
    <div class="topbar-actions">
      <a class="btn btn-primary btn-sm" href="keys.html?new=1" id="quick-new">${icon("plus")}<span class="qa-label">New key</span></a>
      <button class="btn btn-ghost btn-icon theme-toggle" type="button" data-theme-toggle aria-label="Toggle theme">${icon("moon", "icon-moon")}${icon("sun", "icon-sun")}</button>
      <div class="dropdown" id="notif-dd">
        <button class="btn btn-ghost btn-icon notif-btn" data-dropdown-trigger aria-label="Notifications" aria-haspopup="true">${icon("bell")}<span class="notif-count hidden" id="notif-count"></span></button>
        <div class="dropdown-menu notif-menu" role="menu">
          <div class="dropdown-head" style="display:flex;justify-content:space-between;align-items:center">
            <strong style="font-size:var(--text-sm)">Notifications</strong><a class="muted" style="font-size:var(--text-xs)" href="settings.html#notifications">Preferences</a>
          </div>
          <div id="notif-list"><div class="notif-item"><span class="spinner"></span></div></div>
        </div>
      </div>
      <div class="dropdown" id="user-dd">
        <button class="user-btn" data-dropdown-trigger aria-label="Account menu" aria-haspopup="true"><span class="avatar">${esc(initials(name))}</span></button>
        <div class="dropdown-menu" role="menu">
          <div class="dropdown-head"><div style="font-weight:500;font-size:var(--text-sm)">${esc(name)}</div><div class="muted" style="font-size:var(--text-xs);overflow:hidden;text-overflow:ellipsis">${esc(u.email)}</div></div>
          <div class="dropdown-sep"></div>
          <a class="dropdown-item" href="profile.html">${icon("user")}Profile</a>
          <a class="dropdown-item" href="settings.html">${icon("settings")}Settings</a>
          <a class="dropdown-item" href="settings.html#security">${icon("shield")}Security</a>
          <a class="dropdown-item" href="docs.html">${icon("book")}Documentation</a>
          <div class="dropdown-sep"></div>
          <button class="dropdown-item is-danger" id="menu-logout">${icon("logout")}Logout</button>
        </div>
      </div>
    </div>`;

  const app = $("#app");
  const scrim = $(".drawer-scrim");
  const closeDrawer = () => app.classList.remove("is-drawer-open");
  $("#drawer-btn").addEventListener("click", () => app.classList.add("is-drawer-open"));
  scrim?.addEventListener("click", closeDrawer);
  $$("#sidebar a").forEach((a) => a.addEventListener("click", closeDrawer));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });

  const form = $("#global-search");
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const q = form.q.value.trim();
    window.location.href = `keys.html${q ? `?search=${encodeURIComponent(q)}` : ""}`;
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName) && !document.querySelector(".modal-root")) {
      e.preventDefault();
      if (form.offsetParent) form.q.focus();
      else window.location.href = "keys.html";
    }
  });
  window.AyakaTheme?.sync();
  $("#menu-logout").addEventListener("click", logout);
  $("#notif-dd").addEventListener("dropdown:open", loadNotifications);
}

async function loadNotifications() {
  const list = $("#notif-list");
  const count = $("#notif-count");
  try {
    const r = await api.get("/dashboard/notifications");
    const items = r.data || [];
    count.textContent = items.length > 9 ? "9+" : String(items.length);
    count.classList.toggle("hidden", items.length === 0);
    if (!list) return;
    list.innerHTML = items.length
      ? items.map((n) => `<div class="notif-item lvl-${esc(n.level)}">${icon(n.level === "error" ? "alertCircle" : "alert")}
          <div style="min-width:0"><div class="notif-title">${esc(n.title)}</div><div class="notif-body">${esc(n.body)}</div><div class="notif-time">${esc(fmtRelative(n.created_at))}</div></div></div>`).join("")
      : `<div class="empty" style="padding:24px 12px"><div class="empty-icon">${icon("bell")}</div><h3>You're all caught up</h3><p>Alerts for expiring keys, API errors and security events appear here.</p></div>`;
  } catch (err) {
    if (list) list.innerHTML = `<div class="notif-item lvl-error">${icon("alertCircle")}<div class="notif-body">${esc(err.message)}</div></div>`;
  }
}

async function checkStatus() {
  const dot = $("#status-dot");
  if (!dot) return;
  try {
    const r = await api.get("/health/database");
    dot.className = "status-dot is-ok";
    dot.title = `Operational · DB ${r.data.latency_ms} ms`;
  } catch {
    dot.className = "status-dot is-down";
    dot.title = "Degraded — database unreachable";
  }
}

async function configBanner() {
  try {
    const r = await api.get("/health");
    const missing = r.data?.configuration?.missing || [];
    if (missing.length) {
      const b = document.createElement("div");
      b.className = "config-banner";
      b.innerHTML = `${icon("alert")}<span>Server is missing <code>${missing.map(esc).join(", ")}</code>. Sessions and API keys use temporary secrets until these environment variables are set. See README → Environment variables.</span>`;
      document.body.prepend(b);
    }
  } catch { /* status dot already reports outages */ }
}

export async function logout() {
  try {
    await api.post("/auth/logout");
  } catch { /* even if the call fails, leave the app */ }
  window.location.href = "login.html?signed_out=1";
}

function redirectToLogin() {
  const next = encodeURIComponent(window.location.pathname.split("/").pop() + window.location.search + window.location.hash);
  window.location.replace(`login.html?next=${next}`);
}

/**
 * Boot an authenticated page.
 * @param {{page: string, crumbs: {label: string, href?: string}[]}} opts
 */
export async function initShell({ page, crumbs }) {
  let data;
  try {
    data = await loadSession();
  } catch (err) {
    $(".app-loading")?.remove();
    document.body.innerHTML = `<div class="container" style="padding:80px 16px;max-width:560px">
      <div class="card"><div class="card-body">
      <div class="empty is-error"><div class="empty-icon">${icon("alertCircle", "icon-lg")}</div>
      <h3>Can't reach the Ayaka Sync API server</h3><p>${esc(err.message)}</p>
      <p class="muted">If this is a new deployment, check that <code>DATABASE_URL</code> is set and migrations have been applied.</p>
      <div style="display:flex;gap:8px;justify-content:center"><button class="btn" id="boot-retry">Retry</button><a class="btn btn-ghost" href="status.html">View status</a></div></div>
      </div></div></div>`;
    document.getElementById("boot-retry")?.addEventListener("click", () => window.location.reload());
    return new Promise(() => {}); // halt the page module without an uncaught error
  }
  if (!data) { redirectToLogin(); return new Promise(() => {}); }
  session.user = data.user;
  session.settings = data.settings;
  setPrefs({ timezone: data.settings.timezone, date_format: data.settings.date_format });

  hydrateIcons();
  renderSidebar(page);
  renderTopbar(crumbs);
  initDropdowns();
  initTooltips();
  bindCopyButtons();
  bindPasswordToggles();
  window.addEventListener("ayaka:session-expired", () => {
    toast.warning("Session expired", "Please sign in again.");
    setTimeout(redirectToLogin, 900);
  });
  checkStatus();
  loadNotifications();
  configBanner();
  $(".app-loading")?.classList.add("is-done");
  setTimeout(() => $(".app-loading")?.remove(), 250);
  return data;
}

export { toastError, API_ROOT };
