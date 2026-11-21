/* Overview page */
import { api } from "./api.js";
import { initShell } from "./shell.js";
import {
  $, $$, codeBadge, debounce, deltaHtml, emptyState, errorState, esc, fmtDate, fmtTime, fmtMs, fmtNum, fmtPct,
  fmtRelative, icon, poll, qs, renderPagination, skeletonRows, tableMessage, toast,
} from "./components.js";
import { applyTheme, axes, C, chartsReady, onThemeChange, upsertChart } from "./charts.js";

const state = { range: "30d", page: 1, search: "", method: "", status: "", charts: {} };
const COLS = 7;

await initShell({ page: "dashboard", crumbs: [{ label: "Overview" }] });
applyTheme();

if (qs("welcome")) {
  toast.success("Welcome to Ayaka Sync API", "Create your first API key to start sending requests.");
  history.replaceState(null, "", "dashboard.html");
}

/* ----------------------------------------------------------- overview */
function statCard(el, { value, foot, sub }) {
  el.querySelector(".stat-value").innerHTML = value;
  el.querySelector(".stat-foot").innerHTML = foot;
  if (sub !== undefined) el.querySelector(".stat-sub")?.replaceChildren(sub);
}

async function loadOverview() {
  const grid = $("#stats");
  grid.setAttribute("aria-busy", "true");
  try {
    const r = await api.get("/dashboard/overview", { range: state.range });
    const d = r.data;
    const label = { "24h": "vs previous 24h", "7d": "vs previous 7d", "30d": "vs previous 30d", "90d": "vs previous 90d" }[state.range];
    statCard($("#stat-total"), { value: fmtNum(d.total_requests.value), foot: deltaHtml(d.total_requests.change, { suffix: label }) });
    statCard($("#stat-keys"), {
      value: `${fmtNum(d.active_keys.value)}<small>/ ${fmtNum(d.active_keys.total)}</small>`,
      foot: `<span>${fmtNum(d.active_keys.created_in_period)} created in this period</span>`,
    });
    statCard($("#stat-success"), {
      value: fmtNum(d.successful_requests.value),
      foot: d.successful_requests.rate === null ? "<span>No traffic in this period</span>"
        : `${deltaHtml(d.successful_requests.change, { suffix: "" })}<span>${fmtPct(d.successful_requests.rate)} success rate</span>`,
    });
    statCard($("#stat-failed"), {
      value: fmtNum(d.failed_requests.value),
      foot: d.failed_requests.rate === null ? "<span>No traffic in this period</span>"
        : `${deltaHtml(d.failed_requests.change, { invert: true, suffix: "" })}<span>${fmtPct(d.failed_requests.rate)} error rate</span>`,
    });
    $("#onboarding").classList.toggle("hidden", d.active_keys.total > 0);
    renderRealtime(d.realtime);
    $("#updated-at-text").textContent = `Updated ${fmtDate(new Date(), { time: true, seconds: true })}`;
  } catch (err) {
    $$(".stat .stat-value", grid).forEach((v) => { v.textContent = "—"; });
    $$(".stat .stat-foot", grid).forEach((v) => { v.innerHTML = `<span style="color:var(--error)">${esc(err.message)}</span>`; });
  } finally {
    grid.removeAttribute("aria-busy");
  }
}

let lastRealtime = null;
function renderRealtime(rt) {
  lastRealtime = rt;
  $("#rt-rpm").textContent = rt.requests_per_minute.toLocaleString("en-US");
  $("#rt-hour").textContent = fmtNum(rt.requests_last_hour);
  $("#rt-success").textContent = rt.success_rate === null ? "—" : fmtPct(rt.success_rate);
  $("#rt-latency").textContent = rt.requests_last_hour ? fmtMs(rt.avg_response_time_ms) : "—";
  $("#rt-last").textContent = rt.last_request_at ? `Last request ${fmtRelative(rt.last_request_at)}` : "No requests received yet";
  const box = $("#rt-chart-box");
  const empty = $("#rt-empty");
  const total = rt.per_minute.reduce((a, b) => a + b.total, 0);
  empty.classList.toggle("hidden", total > 0);
  if (!chartsReady()) { empty.classList.remove("hidden"); empty.querySelector("p").textContent = "Chart library failed to load."; return; }
  const labels = rt.per_minute.map((m) => fmtTime(m.minute));
  upsertChart(state.charts, "rt", box.querySelector("canvas"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: "Successful", data: rt.per_minute.map((m) => m.total - m.failed), backgroundColor: C.secondary, borderRadius: 2, barPercentage: 0.8, categoryPercentage: 0.9 },
        { label: "Failed", data: rt.per_minute.map((m) => m.failed), backgroundColor: C.error, borderRadius: 2, barPercentage: 0.8, categoryPercentage: 0.9 },
      ],
    },
    options: { scales: axes({ stacked: true, suggestedMax: 4 }), interaction: { mode: "index", intersect: false } },
  });
}

/* ----------------------------------------------------- recent activity */
async function loadActivity() {
  const tbody = $("#activity-body");
  tbody.innerHTML = skeletonRows(5, COLS);
  try {
    const r = await api.get("/dashboard/recent-activity", {
      page: state.page, per_page: 10, search: state.search, method: state.method, status: state.status,
    });
    const filtered = state.search || state.method || state.status;
    if (!r.data.length) {
      tbody.innerHTML = tableMessage(COLS, filtered
        ? emptyState({ ic: "search", title: "No matching requests", text: "Try a different search term or clear the filters.", action: '<button class="btn btn-sm" data-clear-filters>Clear filters</button>' })
        : emptyState({ ic: "activity", title: "No API requests yet", text: "Requests made with your API keys appear here in real time. Create a key and call <code>GET /api/v1/example</code> to see your first entry.", action: '<a class="btn btn-sm btn-primary" href="keys.html?new=1">Create API key</a>' }));
    } else {
      tbody.innerHTML = r.data.map((u) => `<tr>
        <td class="td-primary" data-label="Request ID"><span class="mono cell-sub" title="${esc(u.request_id)}">${esc(u.request_id.slice(0, 14))}…</span></td>
        <td data-label="API key"><div class="cell-main">${esc(u.api_key_name)}</div>${u.key_prefix ? `<div class="cell-sub mono">${esc(u.key_prefix)}…</div>` : ""}</td>
        <td data-label="Endpoint"><span class="mono" style="font-size:12px">${esc(u.endpoint)}</span></td>
        <td data-label="Method"><span class="method">${esc(u.method)}</span></td>
        <td data-label="Status">${codeBadge(u.status_code)}</td>
        <td data-label="Response" class="tabular">${fmtMs(u.response_time_ms)}</td>
        <td data-label="Timestamp"><span title="${esc(fmtDate(u.created_at, { time: true, seconds: true }))}">${esc(fmtRelative(u.created_at))}</span></td>
      </tr>`).join("");
    }
    renderPagination($("#activity-pagination"), r.meta, (p) => { state.page = p; loadActivity(); });
  } catch (err) {
    tbody.innerHTML = tableMessage(COLS, errorState(err));
  }
}

$("#activity-card").addEventListener("click", (e) => {
  if (e.target.closest("[data-retry]")) loadActivity();
  if (e.target.closest("[data-clear-filters]")) {
    state.search = state.method = state.status = "";
    $("#act-search").value = ""; $("#act-method").value = ""; $("#act-status").value = "";
    state.page = 1; loadActivity();
  }
});
$("#act-search").addEventListener("input", debounce((e) => { state.search = e.target.value.trim(); state.page = 1; loadActivity(); }, 300));
$("#act-method").addEventListener("change", (e) => { state.method = e.target.value; state.page = 1; loadActivity(); });
$("#act-status").addEventListener("change", (e) => { state.status = e.target.value; state.page = 1; loadActivity(); });

$$("#range button").forEach((b) => b.addEventListener("click", () => {
  $$("#range button").forEach((x) => x.classList.toggle("is-active", x === b));
  state.range = b.dataset.range;
  loadOverview();
}));
$("#refresh-btn").addEventListener("click", () => { loadOverview(); loadActivity(); });

await Promise.all([loadOverview(), loadActivity()]);
onThemeChange(() => { if (lastRealtime) renderRealtime(lastRealtime); });

/* Real-time: poll every 15s while the tab is visible. */
const live = poll(async () => {
  await loadOverview();
  if (state.page === 1 && !state.search && !state.method && !state.status) await loadActivity();
}, 15000);
document.addEventListener("visibilitychange", () => {
  $("#live-dot").classList.toggle("is-paused", document.hidden);
  $("#live-label").textContent = document.hidden ? "Paused" : "Live";
});
window.addEventListener("beforeunload", () => live.stop());
