/* API Keys management page */
import { api } from "./api.js";
import { initShell, session } from "./shell.js";
import {
  $, $$, clearFormErrors, confirmDialog, copyText, debounce, emptyState, envBadge, errorState, esc, fmtDate, fmtMs,
  fmtNum, fmtRelative, icon, openModal, qs, renderPagination, setLoading, showFormErrors, skeletonRows, statusBadge,
  tableMessage, toast, toastError,
} from "./components.js";

const PERMS = [
  ["read", "Read data — GET /records, GET /example"],
  ["write", "Create & update records"],
  ["delete", "Delete records"],
  ["analytics", "Read usage analytics"],
  ["profile", "Read account profile"],
  ["admin", "Full access incl. key management"],
];
const COLS = 8;
const state = { search: "", environment: "", status: "", sort: "created_desc", page: 1, items: [] };

await initShell({ page: "keys", crumbs: [{ label: "API Keys" }] });

/* ------------------------------------------------------------- listing */
function permChips(perms) {
  if (perms.includes("admin")) return '<span class="badge badge-warning">admin</span>';
  const shown = perms.slice(0, 3).map((p) => `<span class="badge badge-mono">${esc(p)}</span>`).join(" ");
  return shown + (perms.length > 3 ? ` <span class="badge" data-tooltip="${esc(perms.slice(3).join(", "))}">+${perms.length - 3}</span>` : "");
}

function expiryNote(k) {
  if (!k.expires_at) return "";
  const ms = new Date(k.expires_at) - Date.now();
  if (ms <= 0) return "";
  const days = Math.ceil(ms / 86400000);
  return days <= 7 ? `<div class="cell-sub" style="color:var(--warning)">Expires in ${days}d</div>` : "";
}

async function load() {
  const tbody = $("#keys-body");
  tbody.innerHTML = skeletonRows(5, COLS);
  try {
    const r = await api.get("/keys", {
      search: state.search, environment: state.environment, status: state.status, sort: state.sort,
      page: state.page, per_page: 20,
    });
    state.items = r.data;
    $("#count-dev").textContent = fmtNum(r.meta.counts.development);
    $("#count-prod").textContent = fmtNum(r.meta.counts.production);
    const filtered = state.search || state.environment || state.status;
    if (!r.data.length) {
      tbody.innerHTML = tableMessage(COLS, filtered
        ? emptyState({ ic: "search", title: "No keys match your filters", text: "Try another search or reset the filters.", action: '<button class="btn btn-sm" data-reset>Reset filters</button>' })
        : emptyState({ ic: "key", title: "No API keys yet", text: "Create a key to authenticate requests from your application. The full key is shown only once.", action: '<button class="btn btn-sm btn-primary" data-new>Create API key</button>' }));
    } else {
      tbody.innerHTML = r.data.map((k) => `<tr data-id="${k.id}">
        <td class="td-primary" data-label="Name"><div class="cell-main">${esc(k.name)}</div>${k.description ? `<div class="cell-sub" style="max-width:260px;overflow:hidden;text-overflow:ellipsis">${esc(k.description)}</div>` : ""}${expiryNote(k)}</td>
        <td data-label="Key prefix"><code class="mono" style="font-size:12px">${esc(k.masked_key)}</code></td>
        <td data-label="Environment">${envBadge(k.environment)}</td>
        <td data-label="Permissions">${permChips(k.permissions)}</td>
        <td data-label="Created"><span title="${esc(fmtDate(k.created_at, { time: true }))}">${esc(fmtDate(k.created_at))}</span></td>
        <td data-label="Last used"><span title="${k.last_used_at ? esc(fmtDate(k.last_used_at, { time: true, seconds: true })) : "Never used"}">${esc(fmtRelative(k.last_used_at))}</span></td>
        <td data-label="Status">${statusBadge(k.status)}</td>
        <td class="actions"><button class="btn btn-ghost btn-sm btn-icon" data-menu="${k.id}" aria-label="Actions for ${esc(k.name)}" aria-haspopup="true">${icon("more")}</button></td>
      </tr>`).join("");
    }
    renderPagination($("#keys-pagination"), r.meta, (p) => { state.page = p; load(); });
  } catch (err) {
    tbody.innerHTML = tableMessage(COLS, errorState(err));
  }
}

/* -------------------------------------------------- floating row menu */
let menuEl = null;
function closeMenu() { menuEl?.remove(); menuEl = null; }
function openMenu(btn, key) {
  closeMenu();
  const revoked = key.status === "revoked";
  menuEl = document.createElement("div");
  menuEl.className = "dropdown is-open";
  menuEl.style.position = "fixed";
  menuEl.style.zIndex = "80";
  menuEl.innerHTML = `<div class="dropdown-menu" role="menu" style="position:static;opacity:1;transform:none;pointer-events:auto">
    <button class="dropdown-item" data-act="view">${icon("eye")}View details</button>
    ${revoked ? "" : `<button class="dropdown-item" data-act="edit">${icon("pencil")}Edit</button>
    <button class="dropdown-item" data-act="copy-prefix">${icon("copy")}Copy prefix</button>
    <button class="dropdown-item" data-act="toggle">${icon("power")}${key.status === "disabled" ? "Enable" : "Disable"}</button>
    <button class="dropdown-item" data-act="regenerate">${icon("rotate")}Regenerate</button>
    <div class="dropdown-sep"></div>
    <button class="dropdown-item is-danger" data-act="revoke">${icon("ban")}Revoke</button>`}
    <button class="dropdown-item is-danger" data-act="delete">${icon("trash")}Delete</button>
  </div>`;
  document.body.appendChild(menuEl);
  const r = btn.getBoundingClientRect();
  const m = menuEl.getBoundingClientRect();
  let top = r.bottom + 6;
  if (top + m.height > window.innerHeight - 8) top = Math.max(8, r.top - m.height - 6);
  menuEl.style.top = `${top}px`;
  menuEl.style.left = `${Math.max(8, Math.min(r.right - m.width, window.innerWidth - m.width - 8))}px`;
  menuEl.addEventListener("click", (e) => {
    const act = e.target.closest("[data-act]")?.dataset.act;
    if (!act) return;
    closeMenu();
    ACTIONS[act](key);
  });
  menuEl.querySelector(".dropdown-item")?.focus();
}
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-menu]");
  if (b) {
    e.stopPropagation();
    const key = state.items.find((k) => k.id === b.dataset.menu);
    if (menuEl && menuEl.dataset.for === key.id) { closeMenu(); return; }
    openMenu(b, key);
    menuEl.dataset.for = key.id;
    return;
  }
  if (menuEl && !menuEl.contains(e.target)) closeMenu();
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeMenu(); });
window.addEventListener("scroll", closeMenu, true);
window.addEventListener("resize", closeMenu);

/* --------------------------------------------------------- key forms */
function permGrid(selected, name = "permissions") {
  return `<div class="perm-grid">${PERMS.map(([p, d]) => `<label class="perm-option">
      <span class="checkbox"><input type="checkbox" name="${name}" value="${p}" ${selected.includes(p) ? "checked" : ""}></span>
      <div><strong>${p}</strong><span>${esc(d)}</span></div></label>`).join("")}</div>`;
}

function toLocalInput(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function expiryField(defaultDays, current = null) {
  const opts = [["0", "Never"], ["7", "7 days"], ["30", "30 days"], ["90", "90 days"], ["365", "1 year"], ["custom", "Custom date"]];
  const sel = current ? "custom" : String(defaultDays || 0);
  const known = opts.some(([v]) => v === sel);
  return `<div class="field">
      <label class="label" for="f-exp">Expiration <span class="optional">Optional</span></label>
      <select class="select" id="f-exp" name="expiry">${opts.map(([v, l]) => `<option value="${v}" ${v === (known ? sel : "custom") ? "selected" : ""}>${l}</option>`).join("")}</select>
      <input class="input ${sel === "custom" || !known ? "" : "hidden"}" type="datetime-local" name="expires_at" value="${current ? toLocalInput(current) : ""}" aria-label="Custom expiration date">
      <div class="field-error" data-error-for="expires_at"></div>
    </div>`;
}

function readExpiry(form) {
  const v = form.expiry.value;
  if (v === "0") return { expires_at: null, never: true };
  if (v === "custom") {
    if (!form.expires_at.value) return { error: "Pick an expiration date" };
    const d = new Date(form.expires_at.value);
    if (Number.isNaN(d.getTime()) || d <= new Date()) return { error: "Expiration must be in the future" };
    return { expires_at: d.toISOString() };
  }
  return { expires_at: new Date(Date.now() + Number(v) * 86400000).toISOString() };
}

function wireForm(form) {
  form.expiry.addEventListener("change", () => form.expires_at.classList.toggle("hidden", form.expiry.value !== "custom"));
  const adminBox = form.querySelector('input[value="admin"]');
  const pwField = form.querySelector("#admin-pw");
  const sync = () => pwField.classList.toggle("hidden", !adminBox.checked || adminBox.dataset.had === "1");
  adminBox.addEventListener("change", sync);
  sync();
}

function readCommon(form) {
  const perms = $$('input[name="permissions"]:checked', form).map((i) => i.value);
  const endpoints = form.allowed_endpoints.value.split(/[\n,]/).map((s) => s.trim()).filter(Boolean);
  const errs = [];
  if (!form.name.value.trim()) errs.push({ field: "name", message: "Name is required" });
  if (!perms.length) errs.push({ field: "permissions", message: "Select at least one permission" });
  const rl = Number(form.rate_limit.value);
  if (!Number.isInteger(rl) || rl < 1 || rl > 10000) errs.push({ field: "rate_limit", message: "Use a whole number between 1 and 10,000" });
  const bad = endpoints.find((e) => !/^\/api\/v1\/[a-zA-Z0-9/_\-*{}]*$/.test(e));
  if (bad) errs.push({ field: "allowed_endpoints", message: `Invalid pattern “${bad}”. Use paths like /api/v1/records/*` });
  return { perms, endpoints, rl, errs };
}

function keyFormBody(k, prefs) {
  const isEdit = !!k;
  return `<form id="key-form" novalidate class="modal-form" style="display:flex;flex-direction:column;gap:var(--s-4)">
    <div class="field"><label class="label" for="f-name">Name</label><input class="input" id="f-name" name="name" maxlength="80" placeholder="e.g. Production backend" value="${esc(k?.name || "")}" autofocus><div class="field-error" data-error-for="name"></div></div>
    <div class="field"><label class="label" for="f-desc">Description <span class="optional">Optional</span></label><textarea class="textarea" id="f-desc" name="description" maxlength="500" rows="2" placeholder="What is this key used for?">${esc(k?.description || "")}</textarea></div>
    ${isEdit ? "" : `<div class="field"><span class="label">Environment</span>
      <div class="chip-group" role="radiogroup">
        <label class="chip-check"><input type="radio" name="environment" value="development" ${prefs.default_environment !== "production" ? "checked" : ""}><span>Development · ayk_test_</span></label>
        <label class="chip-check"><input type="radio" name="environment" value="production" ${prefs.default_environment === "production" ? "checked" : ""}><span>Production · ayk_live_</span></label>
      </div></div>`}
    <div class="field"><span class="label">Permissions <span class="optional">Least privilege — grant only what you need</span></span>${permGrid(k?.permissions || ["read"])}<div class="field-error" data-error-for="permissions"></div></div>
    <div class="field hidden" id="admin-pw"><label class="label" for="f-pw">Confirm with your password</label><input class="input" id="f-pw" name="current_password" type="password" autocomplete="current-password"><div class="hint">The admin permission can manage other keys. Your password is required to grant it.</div><div class="field-error" data-error-for="current_password"></div></div>
    <div class="field-row">
      <div class="field"><label class="label" for="f-rl">Rate limit <span class="optional">req / min</span></label><input class="input" id="f-rl" name="rate_limit" type="number" min="1" max="10000" step="1" value="${k?.rate_limit ?? prefs.default_rate_limit}"><div class="field-error" data-error-for="rate_limit"></div></div>
      ${expiryField(prefs.default_key_expiration_days, k?.expires_at)}
    </div>
    <div class="field"><label class="label" for="f-ep">Allowed endpoints <span class="optional">Optional · one per line</span></label><textarea class="textarea mono" id="f-ep" name="allowed_endpoints" rows="2" placeholder="/api/v1/example&#10;/api/v1/records/*" style="font-size:12.5px">${esc((k?.allowed_endpoints || []).join("\n"))}</textarea><div class="hint">Leave empty to allow every endpoint the permissions cover. <code>*</code> matches any suffix.</div><div class="field-error" data-error-for="allowed_endpoints"></div></div>
    ${isEdit ? `<label class="setting-row" style="padding:0;border:0"><div><div class="t">Enabled</div><div class="d">Disabled keys are rejected but can be re-enabled later.</div></div><span class="switch"><input type="checkbox" name="enabled" ${k.status !== "disabled" ? "checked" : ""}><span></span></span></label>` : ""}
  </form>`;
}

function openCreate() {
  const prefs = session.settings;
  const m = openModal({
    title: "Create API key", description: "The full key is displayed once after creation. Store it in a secrets manager.",
    size: "lg", body: keyFormBody(null, prefs),
    footer: '<button class="btn" data-close>Cancel</button><button class="btn btn-primary" id="create-submit">Create key</button>',
  });
  const form = m.root.querySelector("#key-form");
  wireForm(form);
  const submit = async (e) => {
    e?.preventDefault();
    clearFormErrors(form);
    const { perms, endpoints, rl, errs } = readCommon(form);
    const exp = readExpiry(form);
    if (exp.error) errs.push({ field: "expires_at", message: exp.error });
    if (perms.includes("admin") && !form.current_password.value) errs.push({ field: "current_password", message: "Password required for admin" });
    if (errs.length) { showFormErrors(form, { details: errs }); return; }
    const btn = m.root.querySelector("#create-submit");
    setLoading(btn, true, "Creating…");
    try {
      const body = {
        name: form.name.value.trim(), description: form.description.value.trim(),
        environment: form.environment.value, permissions: perms, rate_limit: rl, allowed_endpoints: endpoints,
      };
      if (exp.expires_at) body.expires_at = exp.expires_at;
      if (perms.includes("admin")) body.current_password = form.current_password.value;
      const r = await api.post("/keys", body);
      m.close();
      showSecret(r.data, "API key created");
      load();
    } catch (err) {
      setLoading(btn, false);
      if (!showFormErrors(form, err)) toastError(err, "Could not create key");
    }
  };
  m.root.querySelector("#create-submit").addEventListener("click", submit);
  form.addEventListener("submit", submit);
}

function showSecret(k, title) {
  const m = openModal({
    title, dismissible: false, size: "lg",
    description: `Copy your <strong>${esc(k.environment)}</strong> key now. For your security, it will <strong>never be shown again</strong> — only a hash is stored.`,
    body: `<div class="secret-box"><code id="secret-value">${esc(k.secret)}</code><button class="btn btn-sm" id="copy-secret">${icon("copy")}<span>Copy</span></button></div>
      <div class="callout callout-warning">${icon("alert")}<div>Treat this key like a password. Don't commit it to git or expose it in client-side code. If it leaks, regenerate or revoke it immediately.</div></div>
      <dl class="dl"><dt>Name</dt><dd>${esc(k.name)}</dd><dt>Prefix</dt><dd class="mono">${esc(k.key_prefix)}</dd><dt>Permissions</dt><dd>${esc(k.permissions.join(", "))}</dd><dt>Rate limit</dt><dd>${fmtNum(k.rate_limit)} req/min</dd><dt>Expires</dt><dd>${k.expires_at ? esc(fmtDate(k.expires_at, { time: true })) : "Never"}</dd></dl>
      <div class="code"><div class="code-head"><span class="code-lang">Test it</span></div><pre>curl ${esc(location.origin)}/api/v1/example \\\n  -H "Authorization: Bearer ${esc(k.secret)}"</pre></div>
      <label class="checkbox"><input type="checkbox" id="ack"> I have copied and stored this key securely</label>`,
    footer: '<button class="btn btn-primary" id="secret-done" disabled>Done</button>',
  });
  const copyBtn = m.root.querySelector("#copy-secret");
  const ack = m.root.querySelector("#ack");
  const done = m.root.querySelector("#secret-done");
  copyBtn.addEventListener("click", async () => {
    const ok = await copyText(k.secret);
    if (ok) {
      copyBtn.innerHTML = `${icon("check")}<span>Copied</span>`;
      toast.success("Copied to clipboard", "Paste it into your environment variables.");
      ack.checked = true; done.disabled = false;
    } else toast.error("Copy failed", "Select the key and copy it manually.");
  });
  ack.addEventListener("change", () => { done.disabled = !ack.checked; });
  done.addEventListener("click", () => { k.secret = null; m.close(); });
}

function openEdit(k) {
  const m = openModal({
    title: "Edit API key", description: `<code>${esc(k.masked_key)}</code>`, size: "lg",
    body: keyFormBody(k, session.settings),
    footer: '<button class="btn" data-close>Cancel</button><button class="btn btn-primary" id="edit-submit">Save changes</button>',
  });
  const form = m.root.querySelector("#key-form");
  const adminBox = form.querySelector('input[value="admin"]');
  if (k.permissions.includes("admin")) adminBox.dataset.had = "1";
  wireForm(form);
  const submit = async (e) => {
    e?.preventDefault();
    clearFormErrors(form);
    const { perms, endpoints, rl, errs } = readCommon(form);
    const exp = readExpiry(form);
    if (exp.error) errs.push({ field: "expires_at", message: exp.error });
    const addingAdmin = perms.includes("admin") && !k.permissions.includes("admin");
    if (addingAdmin && !form.current_password.value) errs.push({ field: "current_password", message: "Password required for admin" });
    if (errs.length) { showFormErrors(form, { details: errs }); return; }
    const body = {
      name: form.name.value.trim(), description: form.description.value.trim(), permissions: perms,
      rate_limit: rl, allowed_endpoints: endpoints, enabled: form.enabled.checked,
    };
    if (exp.never) { if (k.expires_at) body.clear_expiration = true; }
    else if (form.expiry.value === "custom" && toLocalInput(k.expires_at) === form.expires_at.value) { /* unchanged */ }
    else body.expires_at = exp.expires_at;
    if (addingAdmin) body.current_password = form.current_password.value;
    const btn = m.root.querySelector("#edit-submit");
    setLoading(btn, true, "Saving…");
    try {
      const r = await api.patch(`/keys/${k.id}`, body);
      m.close();
      toast.success(r.message === "No changes" ? "No changes" : "API key updated", k.name);
      load();
    } catch (err) {
      setLoading(btn, false);
      if (!showFormErrors(form, err)) toastError(err, "Could not update key");
    }
  };
  m.root.querySelector("#edit-submit").addEventListener("click", submit);
  form.addEventListener("submit", submit);
}

async function openDetails(k) {
  const m = openModal({ title: k.name, description: `<code>${esc(k.masked_key)}</code>`, size: "lg", body: '<div class="skeleton sk-line" style="width:60%"></div><div class="skeleton sk-line" style="width:80%"></div>' });
  try {
    const r = await api.get(`/keys/${k.id}`);
    const d = r.data;
    const u = d.usage_30d;
    m.el.querySelector(".modal-body").innerHTML = `
      <div class="stat-grid cols-4-sm" style="grid-template-columns:repeat(4,minmax(0,1fr))">
        <div class="card stat"><span class="stat-label">Requests (30d)</span><span class="stat-value">${fmtNum(u.total)}</span></div>
        <div class="card stat"><span class="stat-label">Successful</span><span class="stat-value">${fmtNum(u.successful)}</span></div>
        <div class="card stat"><span class="stat-label">Failed</span><span class="stat-value">${fmtNum(u.failed)}</span></div>
        <div class="card stat"><span class="stat-label">Avg latency</span><span class="stat-value" style="font-size:20px">${u.total ? fmtMs(u.avg_response_time_ms) : "—"}</span></div>
      </div>
      <dl class="dl">
        <dt>Status</dt><dd>${statusBadge(d.status)}</dd>
        <dt>Environment</dt><dd>${envBadge(d.environment)}</dd>
        <dt>Key ID</dt><dd class="mono" style="font-size:12px">${esc(d.id)}</dd>
        <dt>Description</dt><dd>${d.description ? esc(d.description) : '<span class="muted">—</span>'}</dd>
        <dt>Permissions</dt><dd>${d.permissions.map((p) => `<span class="badge badge-mono">${esc(p)}</span>`).join(" ")}</dd>
        <dt>Allowed endpoints</dt><dd>${d.allowed_endpoints.length ? d.allowed_endpoints.map((e) => `<code class="mono" style="font-size:12px">${esc(e)}</code>`).join("<br>") : '<span class="muted">All endpoints covered by permissions</span>'}</dd>
        <dt>Rate limit</dt><dd>${fmtNum(d.rate_limit)} requests / minute</dd>
        <dt>Created</dt><dd>${esc(fmtDate(d.created_at, { time: true }))}</dd>
        <dt>Last used</dt><dd>${d.last_used_at ? `${esc(fmtDate(d.last_used_at, { time: true, seconds: true }))} <span class="muted">(${esc(fmtRelative(d.last_used_at))})</span>` : "Never"}</dd>
        <dt>Expires</dt><dd>${d.expires_at ? esc(fmtDate(d.expires_at, { time: true })) : "Never"}</dd>
        ${d.revoked_at ? `<dt>Revoked</dt><dd>${esc(fmtDate(d.revoked_at, { time: true }))}</dd>` : ""}
      </dl>
      <a class="btn btn-sm" style="align-self:flex-start" href="analytics.html?key=${d.id}">${icon("chart")}View analytics for this key</a>`;
  } catch (err) {
    m.el.querySelector(".modal-body").innerHTML = errorState(err);
  }
}

const ACTIONS = {
  view: openDetails,
  edit: openEdit,
  "copy-prefix": async (k) => { if (await copyText(k.key_prefix)) toast.success("Prefix copied", k.key_prefix); },
  toggle: async (k) => {
    const enable = k.status === "disabled";
    if (!enable) {
      const ok = await confirmDialog({ title: "Disable API key?", message: `Requests using <strong>${esc(k.name)}</strong> will be rejected with <code>API_KEY_DISABLED</code> until you enable it again.`, confirmText: "Disable" });
      if (!ok) return;
    }
    try {
      await api.patch(`/keys/${k.id}`, { enabled: enable });
      toast.success(enable ? "API key enabled" : "API key disabled", k.name);
      load();
    } catch (err) { toastError(err); }
  },
  regenerate: async (k) => {
    const ok = await confirmDialog({ title: "Regenerate API key?", message: `A new secret will be issued for <strong>${esc(k.name)}</strong>. The current secret stops working <strong>immediately</strong> — update every application that uses it.`, confirmText: "Regenerate", danger: true });
    if (!ok) return;
    try {
      const r = await api.post(`/keys/${k.id}/regenerate`);
      showSecret(r.data, "API key regenerated");
      load();
    } catch (err) { toastError(err); }
  },
  revoke: async (k) => {
    const ok = await confirmDialog({ title: "Revoke API key?", message: `<strong>${esc(k.name)}</strong> will be permanently revoked. Requests using it will fail with <code>API_KEY_REVOKED</code>. This can't be undone.`, confirmText: "Revoke key", danger: true, requireText: k.name.length <= 40 ? k.name : "REVOKE" });
    if (!ok) return;
    try {
      await api.post(`/keys/${k.id}/revoke`);
      toast.success("API key revoked", k.name);
      load();
    } catch (err) { toastError(err); }
  },
  delete: async (k) => {
    const ok = await confirmDialog({ title: "Delete API key?", message: `<strong>${esc(k.name)}</strong> and its configuration will be deleted. Historical usage stays in analytics as “Deleted key”. This can't be undone.`, confirmText: "Delete key", danger: true, requireText: "DELETE" });
    if (!ok) return;
    try {
      await api.del(`/keys/${k.id}`);
      toast.success("API key deleted", k.name);
      if (state.items.length === 1 && state.page > 1) state.page--;
      load();
    } catch (err) { toastError(err); }
  },
};

/* --------------------------------------------------------- toolbar */
const searchInput = $("#key-search");
const initial = qs("search");
if (initial) { state.search = initial; searchInput.value = initial; }
searchInput.addEventListener("input", debounce(() => { state.search = searchInput.value.trim(); state.page = 1; load(); }, 300));
$("#key-env").addEventListener("change", (e) => { state.environment = e.target.value; state.page = 1; load(); });
$("#key-status").addEventListener("change", (e) => { state.status = e.target.value; state.page = 1; load(); });
$("#key-sort").addEventListener("change", (e) => { state.sort = e.target.value; state.page = 1; load(); });
$("#new-key").addEventListener("click", openCreate);
$("#keys-card").addEventListener("click", (e) => {
  if (e.target.closest("[data-new]")) openCreate();
  if (e.target.closest("[data-retry]")) load();
  if (e.target.closest("[data-reset]")) {
    state.search = state.environment = state.status = ""; state.page = 1;
    searchInput.value = ""; $("#key-env").value = ""; $("#key-status").value = "";
    load();
  }
});

await load();
if (qs("new")) { history.replaceState(null, "", "keys.html"); openCreate(); }
