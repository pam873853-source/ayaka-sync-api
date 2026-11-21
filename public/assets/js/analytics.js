/* Analytics page — every number comes from the api_usage table. */
import { api } from "./api.js";
import { initShell } from "./shell.js";
import {
  $, $$, deltaHtml, emptyState, errorState, esc, fmtBucket, fmtDate, fmtMs, fmtNum, fmtPct, poll, qs, toast,
} from "./components.js";
import { applyTheme, axes, C, chartsReady, onThemeChange, lineGradient, upsertChart } from "./charts.js";

await initShell({ page: "analytics", crumbs: [{ label: "Analytics" }] });
applyTheme();

const state = { range: "7d", start: "", end: "", key: qs("key") || "", charts: {}, loading: false };

function params() {
  const p = { range: state.range, api_key_id: state.key };
  if (state.range === "custom") { p.start = state.start; p.end = state.end; }
  return p;
}

function setOverlay(id, html) {
  const box = $(`#${id}`);
  let ov = box.querySelector(".chart-overlay");
  if (!html) { ov?.remove(); return; }
  if (!ov) { ov = document.createElement("div"); ov.className = "chart-overlay"; box.appendChild(ov); }
  ov.innerHTML = html;
}
const LOADING = '<span class="spinner" aria-label="Loading"></span>';
const NO_DATA = (t = "No requests in this period") => `<div class="empty" style="padding:0"><h3>${t}</h3><p>Make requests with an API key to populate this chart.</p></div>`;

function stat(id, value, foot = "") {
  const el = $(`#${id}`);
  el.querySelector(".stat-value").innerHTML = value;
  el.querySelector(".stat-foot").innerHTML = foot;
}

function bucketLabel(b, unit) {
  if (unit === "hour") return state.range === "24h" ? fmtBucket(b, "hour") : `${fmtBucket(b, "day")} ${fmtBucket(b, "hour")}`;
  return fmtBucket(b, "day");
}

async function loadOverview() {
  const r = await api.get("/analytics/overview", params());
  const d = r.data;
  const ch = d.change;
  stat("a-total", fmtNum(d.total), deltaHtml(ch.total, { suffix: "vs previous period" }));
  stat("a-today", fmtNum(d.calendar.today), `<span>${fmtNum(d.calendar.all_time)} all time</span>`);
  stat("a-week", fmtNum(d.calendar.this_week), "<span>since Monday</span>");
  stat("a-month", fmtNum(d.calendar.this_month), "<span>since the 1st</span>");
  stat("a-success", d.success_rate === null ? "—" : fmtPct(d.success_rate), `<span>${fmtNum(d.success)} successful</span>`);
  stat("a-error", d.error_rate === null ? "—" : fmtPct(d.error_rate), `<span>${fmtNum(d.failed)} failed</span>`);
  stat("a-latency", d.total ? fmtMs(d.avg_response_time_ms) : "—", d.total ? `${deltaHtml(ch.avg_response_time_ms, { invert: true, suffix: "" })}<span>p95 ${fmtMs(d.p95_response_time_ms)}</span>` : "<span>no traffic</span>");
  stat("a-peak", d.peak ? fmtNum(d.peak.total) : "—", d.peak ? `<span>${esc(r.meta.bucket === "hour" ? fmtDate(d.peak.bucket + "Z", { time: true, tz: "UTC" }) : fmtDate(d.peak.bucket + "Z", { tz: "UTC" }))} · per ${r.meta.bucket}</span>` : "<span>no traffic</span>");
  $("#period-label").textContent = `${fmtDate(r.meta.start)} – ${fmtDate(r.meta.end)} · ${r.meta.timezone}`;
  return d;
}

async function loadSeries() {
  const r = await api.get("/analytics/requests", params());
  const { series, status_codes: codes } = r.data;
  const unit = r.meta.bucket;
  const labels = series.map((b) => bucketLabel(b.bucket, unit));
  const total = series.reduce((a, b) => a + b.total, 0);
  if (!chartsReady()) { ["c-requests", "c-split"].forEach((id) => setOverlay(id, NO_DATA("Chart library failed to load"))); return; }
  const canvas = $("#c-requests canvas");
  upsertChart(state.charts, "requests", canvas, {
    type: "line",
    data: { labels, datasets: [{ label: "Requests", data: series.map((b) => b.total), borderColor: C.white, backgroundColor: lineGradient(canvas.getContext("2d"), C.fill), fill: true, tension: 0.3, pointRadius: 0, pointHoverRadius: 4, borderWidth: 1.75 }] },
    options: { scales: axes({ suggestedMax: 5 }), interaction: { mode: "index", intersect: false } },
  });
  setOverlay("c-requests", total ? "" : NO_DATA());

  upsertChart(state.charts, "split", $("#c-split canvas"), {
    type: "bar",
    data: { labels, datasets: [
      { label: "Successful", data: series.map((b) => b.success), backgroundColor: C.secondary, borderRadius: 2, maxBarThickness: 22 },
      { label: "Failed", data: series.map((b) => b.failed), backgroundColor: C.error, borderRadius: 2, maxBarThickness: 22 },
    ] },
    options: { scales: axes({ stacked: true, suggestedMax: 5 }), interaction: { mode: "index", intersect: false } },
  });
  setOverlay("c-split", total ? "" : NO_DATA());

  const codesEl = $("#status-codes");
  codesEl.innerHTML = codes.length
    ? codes.map((c) => {
      const cls = c.status_code >= 500 ? "badge-error" : c.status_code >= 400 ? "badge-warning" : "badge-success";
      return `<span class="badge badge-mono ${cls}">${c.status_code} · ${fmtNum(c.total)}</span>`;
    }).join(" ")
    : '<span class="muted" style="font-size:var(--text-xs)">No responses recorded</span>';
}

function barList(el, rows, nameFn, emptyText) {
  if (!rows.length) { el.innerHTML = emptyState({ ic: "chart", title: emptyText, text: "Data appears once requests are made in this period." }); return; }
  const max = Math.max(...rows.map((r) => r.total));
  el.innerHTML = `<div class="bar-list">${rows.map((r) => `<div class="bar-row">
      <span class="name" title="${esc(nameFn(r))}">${nameFn(r, true)}</span>
      <span class="val">${fmtNum(r.total)}${r.failed ? ` <span style="color:var(--error)">· ${fmtNum(r.failed)} failed</span>` : ""}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${Math.max(2, (r.total / max) * 100).toFixed(1)}%"></div></div>
    </div>`).join("")}</div>`;
}

async function loadBreakdowns() {
  const [eps, keys] = await Promise.all([
    api.get("/analytics/endpoints", { ...params(), api_key_id: undefined, limit: 8 }),
    api.get("/analytics/keys", { ...params(), api_key_id: undefined, limit: 8 }),
  ]);
  barList($("#by-endpoint"), eps.data, (r, html) => html ? `<span class="method">${esc(r.method)}</span> ${esc(r.endpoint)}` : `${r.method} ${r.endpoint}`, "No endpoint traffic");
  barList($("#by-key"), keys.data, (r, html) => html ? `${esc(r.name || "Deleted key")} <span class="muted">${esc(r.key_prefix || "")}</span>` : r.name || "Deleted key", "No key traffic");
}

async function loadLatency() {
  const r = await api.get("/analytics/response-times", params());
  const series = r.data.series;
  const has = series.some((b) => b.avg_response_time_ms !== null);
  const sparse = series.filter((b) => b.avg_response_time_ms !== null).length < 3; // lines need ≥2 points: show dots
  $("#lat-summary").textContent = has ? `avg ${fmtMs(r.data.avg_response_time_ms)} · p95 ${fmtMs(r.data.p95_response_time_ms)}` : "";
  if (!chartsReady()) return;
  upsertChart(state.charts, "latency", $("#c-latency canvas"), {
    type: "line",
    data: { labels: series.map((b) => bucketLabel(b.bucket, r.meta.bucket)), datasets: [
      { label: "Average (ms)", data: series.map((b) => b.avg_response_time_ms), borderColor: C.white, backgroundColor: C.white, tension: 0.3, pointRadius: sparse ? 3 : 0, pointHoverRadius: 4, borderWidth: 1.75, spanGaps: true },
      { label: "Max (ms)", data: series.map((b) => b.max_response_time_ms), borderColor: C.grey, backgroundColor: C.grey, borderDash: [4, 4], tension: 0.3, pointRadius: sparse ? 3 : 0, pointHoverRadius: 4, borderWidth: 1.25, spanGaps: true },
    ] },
    options: { scales: axes({ yTitle: "ms", suggestedMax: 10 }), interaction: { mode: "index", intersect: false } },
  });
  setOverlay("c-latency", has ? "" : NO_DATA());
}

async function loadAll({ quiet = false } = {}) {
  if (state.loading) return;
  state.loading = true;
  if (!quiet) {
    $$(".stat .stat-value").forEach((v) => { v.innerHTML = '<div class="skeleton sk-num"></div>'; });
    ["c-requests", "c-split", "c-latency"].forEach((id) => setOverlay(id, LOADING));
  }
  $("#a-error-banner").classList.add("hidden");
  try {
    await Promise.all([loadOverview(), loadSeries(), loadBreakdowns(), loadLatency()]);
    $("#updated-at-text").textContent = `Updated ${fmtDate(new Date(), { time: true, seconds: true })}`;
  } catch (err) {
    const b = $("#a-error-banner");
    b.classList.remove("hidden");
    b.querySelector("span.msg").textContent = err.message;
    ["c-requests", "c-split", "c-latency"].forEach((id) => setOverlay(id, errorState(err)));
    $$(".stat .stat-value").forEach((v) => { if (v.querySelector(".skeleton")) v.textContent = "—"; });
  } finally {
    state.loading = false;
  }
}

/* -------------------------------------------------------------- filters */
async function loadKeyOptions() {
  try {
    const r = await api.get("/keys", { per_page: 100, sort: "name" });
    const sel = $("#a-key");
    sel.innerHTML = '<option value="">All API keys</option>' + r.data.map((k) => `<option value="${k.id}">${esc(k.name)} (${esc(k.key_prefix)})</option>`).join("");
    if (state.key && r.data.some((k) => k.id === state.key)) sel.value = state.key;
    else state.key = "";
  } catch { /* the filter simply stays at "All" */ }
}

const today = new Date();
const iso = (d) => d.toISOString().slice(0, 10);
$("#a-start").value = iso(new Date(today.getTime() - 13 * 86400000));
$("#a-end").value = iso(today);
$("#a-start").max = $("#a-end").max = iso(today);

$$("#a-range button").forEach((b) => b.addEventListener("click", () => {
  $$("#a-range button").forEach((x) => x.classList.toggle("is-active", x === b));
  state.range = b.dataset.range;
  $("#custom-range").classList.toggle("hidden", state.range !== "custom");
  if (state.range !== "custom") loadAll();
}));
$("#a-apply").addEventListener("click", () => {
  const s = $("#a-start").value, e = $("#a-end").value;
  if (!s || !e) { toast.warning("Pick both dates"); return; }
  if (s > e) { toast.warning("Invalid range", "Start date must be before end date."); return; }
  if ((new Date(e) - new Date(s)) / 86400000 > 366) { toast.warning("Range too long", "Custom ranges can span at most 366 days."); return; }
  state.start = s; state.end = e;
  loadAll();
});
$("#a-key").addEventListener("change", (e) => { state.key = e.target.value; loadAll(); });
$("#a-refresh").addEventListener("click", () => loadAll());
$("#a-error-banner").addEventListener("click", (e) => { if (e.target.closest("[data-retry]")) loadAll(); });
document.addEventListener("click", (e) => { if (e.target.closest(".chart-overlay [data-retry]")) loadAll(); });

await loadKeyOptions();
await loadAll();
onThemeChange(() => loadAll({ quiet: true }));

const live = poll(() => (state.range === "custom" ? null : loadAll({ quiet: true })), 30000);
document.addEventListener("visibilitychange", () => {
  $("#live-dot").classList.toggle("is-paused", document.hidden);
  $("#live-label").textContent = document.hidden ? "Paused" : "Auto-refresh 30s";
});
window.addEventListener("beforeunload", () => live.stop());
