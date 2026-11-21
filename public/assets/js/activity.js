/* Activity (audit) log page */
import { api } from "./api.js";
import { initShell } from "./shell.js";
import {
  $, debounce, emptyState, errorState, esc, fmtDate, fmtRelative, icon, openModal, renderPagination, setLoading,
  skeletonRows, tableMessage, toast, toastError,
} from "./components.js";

await initShell({ page: "activity", crumbs: [{ label: "Activity Logs" }] });

const COLS = 4;
const state = { page: 1, search: "", event_type: "", start: "", end: "", items: [], typesLoaded: false };
const EVENT_ICON = { auth: "lock", key: "key", profile: "user", password: "shield", settings: "settings" };

function filters() {
  return { search: state.search, event_type: state.event_type, start: state.start, end: state.end };
}

function eventBadge(type) {
  const cls = type === "auth.failed" || type.endsWith("revoked") || type.endsWith("deleted") ? "badge-error"
    : type.endsWith("disabled") || type === "auth.logout_all" ? "badge-warning" : "";
  return `<span class="badge badge-mono ${cls}">${esc(type)}</span>`;
}

function fillTypes(types) {
  if (state.typesLoaded) return;
  state.typesLoaded = true;
  const sel = $("#log-type");
  const groups = { "auth.*": "All authentication", "key.*": "All API key events" };
  sel.innerHTML = '<option value="">All events</option>'
    + Object.entries(groups).map(([v, l]) => `<option value="${v}">${l}</option>`).join("")
    + '<option disabled>──────────</option>'
    + Object.entries(types).map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join("");
}

async function load() {
  const tbody = $("#log-body");
  tbody.innerHTML = skeletonRows(8, COLS);
  try {
    const r = await api.get("/activity", { ...filters(), page: state.page, per_page: 20 });
    fillTypes(r.meta.event_types);
    state.items = r.data;
    const filtered = state.search || state.event_type || state.start || state.end;
    $("#log-total").textContent = `${r.meta.total.toLocaleString("en-US")} event${r.meta.total === 1 ? "" : "s"}`;
    if (!r.data.length) {
      tbody.innerHTML = tableMessage(COLS, filtered
        ? emptyState({ ic: "search", title: "No events match", text: "Adjust the search, event type or date range.", action: '<button class="btn btn-sm" data-reset>Reset filters</button>' })
        : emptyState({ ic: "logs", title: "No activity yet", text: "Sign-ins, API key changes and settings updates will be recorded here." }));
    } else {
      tbody.innerHTML = r.data.map((a) => `<tr class="is-clickable" data-id="${a.id}" tabindex="0">
        <td class="td-primary" data-label="Event"><div style="display:flex;gap:10px;align-items:center"><span class="stat-icon" style="width:28px;height:28px">${icon(EVENT_ICON[a.event_type.split(".")[0]] || "activity")}</span><div style="min-width:0"><div class="cell-main">${esc(a.label)}</div><div class="cell-sub" style="white-space:normal">${esc(a.description)}</div></div></div></td>
        <td data-label="Type">${eventBadge(a.event_type)}</td>
        <td data-label="IP address"><span class="mono" style="font-size:12px">${esc(a.ip_address || "—")}</span></td>
        <td data-label="Time"><span title="${esc(fmtDate(a.created_at, { time: true, seconds: true }))}">${esc(fmtDate(a.created_at, { time: true }))}</span><div class="cell-sub">${esc(fmtRelative(a.created_at))}</div></td>
      </tr>`).join("");
    }
    renderPagination($("#log-pagination"), r.meta, (p) => { state.page = p; load(); });
  } catch (err) {
    tbody.innerHTML = tableMessage(COLS, errorState(err));
  }
}

function showDetail(a) {
  openModal({
    title: a.label, description: esc(a.description), size: "lg",
    body: `<dl class="dl">
      <dt>Event type</dt><dd>${eventBadge(a.event_type)}</dd>
      <dt>Log ID</dt><dd class="mono">${esc(a.id)}</dd>
      <dt>Timestamp</dt><dd>${esc(fmtDate(a.created_at, { time: true, seconds: true }))} <span class="muted">(${esc(new Date(a.created_at).toISOString())})</span></dd>
      <dt>IP address</dt><dd class="mono">${esc(a.ip_address || "—")}</dd>
      <dt>User agent</dt><dd style="font-size:12px">${esc(a.user_agent || "—")}</dd>
    </dl>
    <div class="code"><div class="code-head"><span class="code-lang">metadata</span><button class="btn btn-ghost btn-sm" data-copy-target="#meta-json">${icon("copy")}<span>Copy</span></button></div><pre id="meta-json">${esc(JSON.stringify(a.metadata || {}, null, 2))}</pre></div>
    <p class="hint">Activity logs are append-only: entries cannot be edited or deleted (enforced by a database trigger).</p>`,
  });
}

$("#log-body").addEventListener("click", (e) => {
  if (e.target.closest("[data-retry]")) return load();
  if (e.target.closest("[data-reset]")) {
    Object.assign(state, { search: "", event_type: "", start: "", end: "", page: 1 });
    $("#log-search").value = ""; $("#log-type").value = ""; $("#log-start").value = ""; $("#log-end").value = "";
    return load();
  }
  const row = e.target.closest("tr[data-id]");
  if (row) showDetail(state.items.find((a) => String(a.id) === row.dataset.id));
});
$("#log-body").addEventListener("keydown", (e) => {
  const row = e.target.closest("tr[data-id]");
  if (row && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); showDetail(state.items.find((a) => String(a.id) === row.dataset.id)); }
});

$("#log-search").addEventListener("input", debounce((e) => { state.search = e.target.value.trim(); state.page = 1; load(); }, 300));
$("#log-type").addEventListener("change", (e) => { state.event_type = e.target.value; state.page = 1; load(); });
for (const id of ["log-start", "log-end"]) {
  $(`#${id}`).addEventListener("change", () => {
    const s = $("#log-start").value, en = $("#log-end").value;
    if (s && en && s > en) { toast.warning("Invalid date range", "Start date must be before end date."); return; }
    state.start = s; state.end = en; state.page = 1; load();
  });
}

$("#export-csv").addEventListener("click", async (e) => {
  const btn = e.currentTarget;
  setLoading(btn, true, "Exporting…");
  try {
    const res = await api.raw("/activity/export", filters());
    const blob = await res.blob();
    const name = (res.headers.get("Content-Disposition") || "").match(/filename="([^"]+)"/)?.[1] || "ayaka-activity.csv";
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement("a"), { href: url, download: name });
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    toast.success("Export ready", `${name} downloaded`);
  } catch (err) {
    toastError(err, "Export failed");
  } finally {
    setLoading(btn, false);
  }
});

await load();
