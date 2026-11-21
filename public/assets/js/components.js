/* ==========================================================================
   Reusable UI components: icons, toast, modal, confirm, dropdown, tooltip,
   formatters, skeletons, empty/error states, pagination, helpers.
   ========================================================================== */

/* ---------------------------------------------------------------- icons
   Paths adapted from Lucide (ISC license). */
const P = {
  dashboard: '<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
  key: '<path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z"/><circle cx="16.5" cy="7.5" r=".5" fill="currentColor"/>',
  chart: '<path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
  book: '<path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/>',
  activity: '<path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"/>',
  logs: '<path d="M15 12h-5"/><path d="M15 8h-5"/><path d="M19 17V5a2 2 0 0 0-2-2H4"/><path d="M8 21h12a2 2 0 0 0 2-2v-1a1 1 0 0 0-1-1H11a1 1 0 0 0-1 1v1a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v2a1 1 0 0 0 1 1h3"/>',
  settings: '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
  help: '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
  signal: '<path d="M2 20h.01"/><path d="M7 20v-4"/><path d="M12 20v-8"/><path d="M17 20V8"/><path d="M22 4v16"/>',
  user: '<circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 0 0-16 0"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/>',
  panel: '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 3v18"/><path d="m16 15-3-3 3-3"/>',
  search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  bell: '<path d="M10.268 21a2 2 0 0 0 3.464 0"/><path d="M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326"/>',
  plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
  copy: '<rect width="14" height="14" x="8" y="8" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  more: '<circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>',
  eye: '<path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/>',
  eyeOff: '<path d="M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49"/><path d="M14.084 14.158a3 3 0 0 1-4.242-4.242"/><path d="M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143"/><path d="m2 2 20 20"/>',
  shield: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
  zap: '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>',
  gauge: '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>',
  lock: '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
  server: '<rect width="20" height="8" x="2" y="2" rx="2" ry="2"/><rect width="20" height="8" x="2" y="14" rx="2" ry="2"/><line x1="6" x2="6.01" y1="6" y2="6"/><line x1="6" x2="6.01" y1="18" y2="18"/>',
  code: '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>',
  arrowRight: '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
  arrowUpRight: '<path d="M7 7h10v10"/><path d="M7 17 17 7"/>',
  chevronRight: '<path d="m9 18 6-6-6-6"/>',
  chevronLeft: '<path d="m15 18-6-6 6-6"/>',
  chevronDown: '<path d="m6 9 6 6 6-6"/>',
  refresh: '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
  trash: '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>',
  pencil: '<path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/>',
  ban: '<circle cx="12" cy="12" r="10"/><path d="m4.9 4.9 14.2 14.2"/>',
  rotate: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
  alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  alertCircle: '<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/>',
  checkCircle: '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
  info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
  calendar: '<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/>',
  globe: '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
  clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
  terminal: '<polyline points="4 17 10 11 4 5"/><line x1="12" x2="20" y1="19" y2="19"/>',
  monitor: '<rect width="20" height="14" x="2" y="3" rx="2"/><line x1="8" x2="16" y1="21" y2="21"/><line x1="12" x2="12" y1="17" y2="21"/>',
  phone: '<rect width="14" height="20" x="5" y="2" rx="2" ry="2"/><path d="M12 18h.01"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
  moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
  menu: '<line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="18" y2="18"/>',
  power: '<path d="M12 2v10"/><path d="M18.4 6.6a9 9 0 1 1-12.77.04"/>',
  external: '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
  trendUp: '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
  trendDown: '<polyline points="22 17 13.5 8.5 8.5 13.5 2 7"/><polyline points="16 17 22 17 22 11"/>',
  xCircle: '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
  layers: '<path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/><path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>',
  file: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>',
  mail: '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
  play: '<polygon points="6 3 20 12 6 21 6 3"/>',
  filter: '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>',
  inbox: '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
  sync: '<path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/>',
};

export function icon(name, cls = "") {
  return `<svg class="icon ${cls}" viewBox="0 0 24 24" aria-hidden="true">${P[name] || P.info}</svg>`;
}

/** Replace <span data-icon="name"></span> placeholders with inline SVG. */
export function hydrateIcons(root = document) {
  root.querySelectorAll("[data-icon]").forEach((el) => {
    el.outerHTML = icon(el.dataset.icon, el.className || "");
  });
}

export const LOGO_MARK = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 15 12 4l8 11"/><path d="M8 20h8"/><path d="M8.5 15h7"/></svg>`;

export function logo({ href = "index.html", compact = false } = {}) {
  return `<a class="logo" href="${href}" aria-label="Ayaka Sync API home">
    <span class="logo-mark">${LOGO_MARK}</span>
    ${compact ? "" : '<span class="logo-text"><strong>AYAKA</strong><span>SYNC API</span></span>'}
  </a>`;
}

/* ------------------------------------------------------------- helpers */
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

export function debounce(fn, ms = 300) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

export function setLoading(btn, loading, label) {
  if (!btn) return;
  if (loading) {
    btn.dataset.label = btn.innerHTML;
    btn.classList.add("is-loading");
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner" aria-hidden="true"></span>${label ? `<span>${esc(label)}</span>` : ""}`;
  } else {
    btn.classList.remove("is-loading");
    btn.disabled = false;
    if (btn.dataset.label) btn.innerHTML = btn.dataset.label;
  }
}

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch { ok = false; }
    ta.remove();
    return ok;
  }
}

export function bindCopyButtons(root = document) {
  root.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-copy], [data-copy-target]");
    if (!btn || !root.contains(btn)) return;
    const text = btn.dataset.copy ?? document.querySelector(btn.dataset.copyTarget)?.innerText ?? "";
    const ok = await copyText(text.trim());
    const original = btn.innerHTML;
    btn.innerHTML = ok ? `${icon("check")}<span>Copied</span>` : `${icon("x")}<span>Copy failed</span>`;
    if (btn.classList.contains("btn-icon")) btn.innerHTML = icon(ok ? "check" : "x");
    setTimeout(() => { btn.innerHTML = original; }, 1600);
    if (!ok) toast.error("Copy failed", "Select the text and copy it manually.");
  });
}

/* --------------------------------------------------------- preferences */
export const prefs = { timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC", date_format: "YYYY-MM-DD" };
export function setPrefs(p) { if (p) Object.assign(prefs, p); }

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function parts(date, tz) {
  const f = new Intl.DateTimeFormat("en-GB", {
    timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
    second: "2-digit", hourCycle: "h23",
  });
  const o = {};
  for (const p of f.formatToParts(date)) o[p.type] = p.value;
  return o;
}

export function fmtDate(value, { time = false, seconds = false, tz } = {}) {
  if (!value) return "—";
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  let p;
  try { p = parts(d, tz || prefs.timezone); } catch { p = parts(d, "UTC"); }
  const map = {
    "YYYY-MM-DD": `${p.year}-${p.month}-${p.day}`,
    "DD/MM/YYYY": `${p.day}/${p.month}/${p.year}`,
    "MM/DD/YYYY": `${p.month}/${p.day}/${p.year}`,
    "DD MMM YYYY": `${p.day} ${MONTHS[Number(p.month) - 1]} ${p.year}`,
  };
  const date = map[prefs.date_format] || map["YYYY-MM-DD"];
  if (!time) return date;
  return `${date} ${p.hour}:${p.minute}${seconds ? ":" + p.second : ""}`;
}

export function fmtTime(value) {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  let p;
  try { p = parts(d, prefs.timezone); } catch { p = parts(d, "UTC"); }
  return `${p.hour}:${p.minute}`;
}

/** Naive local bucket string ("2026-01-01T13:00:00") → label in user's date format. */
export function fmtBucket(bucket, unit) {
  const [d, t = "00:00"] = bucket.split("T");
  const [y, m, day] = d.split("-");
  if (unit === "hour") return t.slice(0, 5);
  if (unit === "minute") return t.slice(0, 5);
  const map = {
    "YYYY-MM-DD": `${m}-${day}`, "DD/MM/YYYY": `${day}/${m}`, "MM/DD/YYYY": `${m}/${day}`,
    "DD MMM YYYY": `${day} ${MONTHS[Number(m) - 1]}`,
  };
  return map[prefs.date_format] || `${m}-${day}`;
}

export function fmtRelative(value) {
  if (!value) return "Never";
  const diff = (Date.now() - new Date(value).getTime()) / 1000;
  const abs = Math.abs(diff);
  const fut = diff < 0;
  const unit = abs < 60 ? [Math.round(abs), "s"] : abs < 3600 ? [Math.round(abs / 60), "m"]
    : abs < 86400 ? [Math.round(abs / 3600), "h"] : abs < 86400 * 30 ? [Math.round(abs / 86400), "d"] : null;
  if (!unit) return fmtDate(value);
  if (abs < 10) return "just now";
  return fut ? `in ${unit[0]}${unit[1]}` : `${unit[0]}${unit[1]} ago`;
}

export const fmtNum = (n) => (n === null || n === undefined ? "—" : Number(n).toLocaleString("en-US"));
export function fmtCompact(n) {
  if (n === null || n === undefined) return "—";
  return Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(n);
}
export const fmtPct = (n, d = 1) => (n === null || n === undefined ? "—" : `${Number(n).toFixed(d)}%`);
export const fmtMs = (n) => (n === null || n === undefined ? "—" : `${Math.round(n).toLocaleString("en-US")} ms`);

export function initials(name) {
  const s = String(name || "?").trim();
  const bits = s.split(/[\s._-]+/).filter(Boolean);
  return ((bits[0]?.[0] || "?") + (bits[1]?.[0] || "")).toUpperCase();
}

export function deltaHtml(change, { invert = false, suffix = "vs previous period" } = {}) {
  if (change === null || change === undefined) return `<span class="delta flat">—</span><span>no prior data</span>`;
  const up = change > 0;
  const good = invert ? !up : up;
  const cls = change === 0 ? "flat" : good ? "up" : "down";
  const ic = change === 0 ? "" : icon(up ? "trendUp" : "trendDown");
  return `<span class="delta ${cls}">${ic}${up ? "+" : ""}${change.toFixed(1)}%</span><span>${suffix}</span>`;
}

/* --------------------------------------------------------------- badges */
export function statusBadge(status) {
  const map = {
    active: ["badge-success", "Active"], expired: ["badge-warning", "Expired"],
    revoked: ["badge-error", "Revoked"], disabled: ["", "Disabled"],
  };
  const [cls, label] = map[status] || ["", status];
  return `<span class="badge badge-dot ${cls}">${esc(label)}</span>`;
}

export function codeBadge(code) {
  const cls = code >= 500 ? "badge-error" : code >= 400 ? "badge-warning" : "badge-success";
  return `<span class="badge badge-mono ${cls}">${esc(code)}</span>`;
}

export function envBadge(env) {
  return env === "production" ? '<span class="badge badge-solid">Production</span>' : '<span class="badge">Development</span>';
}

/* ---------------------------------------------------------------- toast */
function toastStack() {
  let el = document.querySelector(".toast-stack");
  if (!el) {
    el = document.createElement("div");
    el.className = "toast-stack";
    el.setAttribute("role", "status");
    el.setAttribute("aria-live", "polite");
    document.body.appendChild(el);
  }
  return el;
}

function showToast(type, title, message = "", timeout = 4200) {
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  const ic = { success: "checkCircle", error: "alertCircle", warning: "alert", info: "info" }[type];
  el.innerHTML = `<span class="toast-icon">${icon(ic)}</span>
    <div class="toast-body"><div class="toast-title">${esc(title)}</div>${message ? `<div class="toast-msg">${esc(message)}</div>` : ""}</div>
    <button class="toast-close" aria-label="Dismiss">${icon("x")}</button>`;
  const close = () => { el.classList.add("is-leaving"); setTimeout(() => el.remove(), 180); };
  el.querySelector(".toast-close").addEventListener("click", close);
  toastStack().appendChild(el);
  if (timeout) setTimeout(close, timeout);
  return close;
}

export const toast = {
  success: (t, m) => showToast("success", t, m),
  error: (t, m) => showToast("error", t, m, 6000),
  warning: (t, m) => showToast("warning", t, m, 5500),
  info: (t, m) => showToast("info", t, m),
};

export function toastError(err, fallback = "Something went wrong") {
  const msg = err?.message || fallback;
  const titles = {
    NETWORK_ERROR: "Connection problem", RATE_LIMIT_EXCEEDED: "Rate limit reached", SESSION_EXPIRED: "Session expired",
    DATABASE_UNAVAILABLE: "Database unavailable", DATABASE_NOT_CONFIGURED: "Database not configured",
    PERMISSION_DENIED: "Permission denied", VALIDATION_ERROR: "Please check the form", CSRF_FAILED: "Security check failed",
  };
  toast.error(titles[err?.code] || fallback, msg);
}

/* ---------------------------------------------------------------- modal */
let modalDepth = 0;
export function openModal({ title, description = "", body = "", footer = "", size = "", onClose, dismissible = true } = {}) {
  const root = document.createElement("div");
  root.className = "modal-root";
  root.innerHTML = `<div class="modal-backdrop"></div>
    <div class="modal ${size ? "modal-" + size : ""}" role="dialog" aria-modal="true" aria-labelledby="m-title-${modalDepth}">
      <div class="modal-header">
        <div><h2 class="modal-title" id="m-title-${modalDepth}">${esc(title)}</h2>${description ? `<p class="modal-desc">${description}</p>` : ""}</div>
        ${dismissible ? `<button class="btn btn-ghost btn-sm btn-icon" data-close aria-label="Close">${icon("x")}</button>` : ""}
      </div>
      <div class="modal-body"></div>
      ${footer ? `<div class="modal-footer">${footer}</div>` : ""}
    </div>`;
  const bodyEl = root.querySelector(".modal-body");
  if (typeof body === "string") bodyEl.innerHTML = body; else if (body) bodyEl.appendChild(body);
  if (!bodyEl.innerHTML.trim()) bodyEl.remove();
  const previouslyFocused = document.activeElement;
  document.body.appendChild(root);
  document.body.classList.add("modal-open");
  modalDepth++;

  let closed = false;
  const close = (result) => {
    if (closed) return;
    closed = true;
    root.remove();
    modalDepth--;
    if (modalDepth <= 0) document.body.classList.remove("modal-open");
    document.removeEventListener("keydown", onKey);
    previouslyFocused?.focus?.();
    onClose?.(result);
  };
  const onKey = (e) => {
    if (e.key === "Escape" && dismissible) { e.stopPropagation(); close(); }
    if (e.key === "Tab") { // focus trap
      const f = $$('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])', root).filter((x) => !x.disabled && x.offsetParent !== null);
      if (!f.length) return;
      if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
      else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
    }
  };
  document.addEventListener("keydown", onKey);
  root.addEventListener("click", (e) => {
    if (e.target.closest("[data-close]")) close();
    if (dismissible && e.target.classList.contains("modal-backdrop")) close();
  });
  setTimeout(() => {
    const first = root.querySelector("[autofocus], .modal-body input, .modal-body select, .modal-body textarea, .modal-footer .btn-primary");
    (first || root.querySelector(".modal")).focus?.();
  }, 30);
  return { root, el: root.querySelector(".modal"), close };
}

/** Confirmation dialog. Resolves to true / {password} / false. */
export function confirmDialog({ title, message, confirmText = "Confirm", danger = false, requireText = null, requirePassword = false } = {}) {
  return new Promise((resolve) => {
    const body = `<p class="text-2" style="font-size:var(--text-sm)">${message}</p>
      ${requireText ? `<div class="field"><label class="label" for="cd-text" style="display:block">Type <code>${esc(requireText)}</code> to confirm</label><input class="input" id="cd-text" autocomplete="off" spellcheck="false"></div>` : ""}
      ${requirePassword ? `<div class="field"><label class="label" for="cd-pass">Current password</label><input class="input" id="cd-pass" type="password" autocomplete="current-password"></div>` : ""}`;
    const m = openModal({
      title, body, size: "sm",
      footer: `<button class="btn" data-close>Cancel</button><button class="btn ${danger ? "btn-danger-solid" : "btn-primary"}" data-ok>${esc(confirmText)}</button>`,
      onClose: (r) => resolve(r ?? false),
    });
    const ok = m.root.querySelector("[data-ok]");
    const txt = m.root.querySelector("#cd-text");
    const pass = m.root.querySelector("#cd-pass");
    const validate = () => { ok.disabled = (txt && txt.value !== requireText) || (pass && !pass.value); };
    txt?.addEventListener("input", validate);
    pass?.addEventListener("input", validate);
    validate();
    const submit = () => { if (!ok.disabled) m.close(requirePassword ? { password: pass.value } : true); };
    ok.addEventListener("click", submit);
    m.root.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.tagName === "INPUT") submit(); });
  });
}

/* ------------------------------------------------------------- dropdown */
export function initDropdowns(root = document) {
  root.addEventListener("click", (e) => {
    const trigger = e.target.closest("[data-dropdown-trigger]");
    const openOnes = $$(".dropdown.is-open");
    if (trigger) {
      const dd = trigger.closest(".dropdown");
      const willOpen = !dd.classList.contains("is-open");
      openOnes.forEach((d) => d.classList.remove("is-open"));
      if (willOpen) {
        dd.classList.add("is-open");
        trigger.setAttribute("aria-expanded", "true");
        dd.dispatchEvent(new CustomEvent("dropdown:open"));
      }
      return;
    }
    if (!e.target.closest(".dropdown-menu")) openOnes.forEach((d) => d.classList.remove("is-open"));
    else if (e.target.closest(".dropdown-item")) openOnes.forEach((d) => d.classList.remove("is-open"));
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") $$(".dropdown.is-open").forEach((d) => d.classList.remove("is-open"));
  });
}

/* -------------------------------------------------------------- tooltip */
export function initTooltips() {
  let bubble = null;
  const show = (el) => {
    hide();
    bubble = document.createElement("div");
    bubble.className = "tooltip-bubble";
    bubble.textContent = el.dataset.tooltip;
    document.body.appendChild(bubble);
    const r = el.getBoundingClientRect();
    const b = bubble.getBoundingClientRect();
    let left = r.left + r.width / 2 - b.width / 2;
    left = Math.max(8, Math.min(left, window.innerWidth - b.width - 8));
    let top = r.top - b.height - 8;
    if (top < 8) top = r.bottom + 8;
    bubble.style.left = `${left}px`;
    bubble.style.top = `${top}px`;
  };
  const hide = () => { bubble?.remove(); bubble = null; };
  document.addEventListener("mouseover", (e) => { const el = e.target.closest("[data-tooltip]"); if (el) show(el); });
  document.addEventListener("mouseout", (e) => { if (e.target.closest("[data-tooltip]")) hide(); });
  document.addEventListener("focusin", (e) => { const el = e.target.closest("[data-tooltip]"); if (el) show(el); });
  document.addEventListener("focusout", hide);
  window.addEventListener("scroll", hide, true);
}

/* ------------------------------------------------- states & skeletons */
export function skeletonRows(rows = 5, cols = 5) {
  const cells = Array.from({ length: cols }, (_, i) => `<td><div class="skeleton sk-line" style="width:${[70, 50, 40, 60, 30][i % 5]}%"></div></td>`).join("");
  return Array.from({ length: rows }, () => `<tr>${cells}</tr>`).join("");
}

export function emptyState({ ic = "inbox", title, text = "", action = "" } = {}) {
  return `<div class="empty fade-in"><div class="empty-icon">${icon(ic, "icon-lg")}</div><h3>${esc(title)}</h3>${text ? `<p>${text}</p>` : ""}${action}</div>`;
}

export function errorState(err, { retryLabel = "Try again" } = {}) {
  const msg = err?.message || "Something went wrong while loading this data.";
  return `<div class="empty is-error fade-in"><div class="empty-icon">${icon("alertCircle", "icon-lg")}</div><h3>Couldn’t load data</h3><p>${esc(msg)}</p><button class="btn btn-sm" data-retry>${icon("refresh")}${esc(retryLabel)}</button></div>`;
}

export function tableMessage(colspan, html) {
  return `<tr class="no-hover"><td colspan="${colspan}" style="padding:0;white-space:normal">${html}</td></tr>`;
}

/* ------------------------------------------------------------ pagination */
export function renderPagination(el, meta, onPage) {
  if (!el) return;
  const { page = 1, total_pages = 1, total = 0, per_page = 20 } = meta || {};
  const from = total ? (page - 1) * per_page + 1 : 0;
  const to = Math.min(page * per_page, total);
  el.innerHTML = `<span class="pagination-info tabular">${total ? `${fmtNum(from)}–${fmtNum(to)} of ${fmtNum(total)}` : "No results"}</span>
    <div class="pagination">
      <button class="btn btn-sm btn-icon" data-pg="prev" ${page <= 1 ? "disabled" : ""} aria-label="Previous page">${icon("chevronLeft")}</button>
      <span class="pagination-info tabular">Page ${page} / ${total_pages}</span>
      <button class="btn btn-sm btn-icon" data-pg="next" ${page >= total_pages ? "disabled" : ""} aria-label="Next page">${icon("chevronRight")}</button>
    </div>`;
  el.querySelector('[data-pg="prev"]').onclick = () => onPage(page - 1);
  el.querySelector('[data-pg="next"]').onclick = () => onPage(page + 1);
}

/* ---------------------------------------------------------- form errors */
export function clearFormErrors(form) {
  $$(".field-error", form).forEach((e) => { e.textContent = ""; });
  $$(".is-invalid", form).forEach((e) => e.classList.remove("is-invalid"));
}

export function showFormErrors(form, err) {
  clearFormErrors(form);
  let placed = false;
  for (const d of err?.details || []) {
    if (!d?.field) continue;
    const input = form.querySelector(`[name="${d.field}"]`);
    const slot = form.querySelector(`[data-error-for="${d.field}"]`);
    if (input) input.classList.add("is-invalid");
    if (slot) { slot.textContent = d.message; placed = true; }
  }
  return placed;
}

/* -------------------------------------------------------------- polling */
/** Calls fn every `interval` ms while the tab is visible. */
export function poll(fn, interval) {
  let timer = null;
  let stopped = false;
  const tick = async () => {
    if (stopped) return;
    try { await fn(); } finally {
      if (!stopped && !document.hidden) timer = setTimeout(tick, interval);
    }
  };
  const onVis = () => {
    clearTimeout(timer);
    if (!document.hidden && !stopped) tick();
  };
  document.addEventListener("visibilitychange", onVis);
  timer = setTimeout(tick, interval);
  return {
    stop() { stopped = true; clearTimeout(timer); document.removeEventListener("visibilitychange", onVis); },
    now() { clearTimeout(timer); tick(); },
    get paused() { return document.hidden; },
  };
}

export function passwordScore(pw) {
  if (!pw) return 0;
  let s = 0;
  if (pw.length >= 8) s++;
  if (pw.length >= 12) s++;
  const classes = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter((r) => r.test(pw)).length;
  if (classes >= 2) s++;
  if (classes >= 3 && pw.length >= 10) s++;
  if (pw.length < 8) s = Math.min(s, 1);
  return Math.min(s, 4);
}

export function bindPasswordToggles(root = document) {
  root.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-toggle-password]");
    if (!btn) return;
    const input = document.getElementById(btn.dataset.togglePassword);
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    btn.innerHTML = icon(show ? "eyeOff" : "eye");
    btn.setAttribute("aria-label", show ? "Hide password" : "Show password");
  });
}

export function qs(name) { return new URLSearchParams(window.location.search).get(name); }
