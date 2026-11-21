/* Settings page */
import { api } from "./api.js";
import { initShell, session } from "./shell.js";
import {
  $, $$, clearFormErrors, confirmDialog, emptyState, errorState, esc, fmtDate, fmtRelative, icon, passwordScore,
  setLoading, setPrefs, showFormErrors, toast, toastError,
} from "./components.js";

await initShell({ page: "settings", crumbs: [{ label: "Settings" }] });

let settings = { ...session.settings };
const user = { ...session.user };

/* ------------------------------------------------------- section nav */
const navLinks = $$(".settings-nav a");
const sections = navLinks.map((a) => $(a.getAttribute("href")));
const spy = new IntersectionObserver((entries) => {
  entries.forEach((en) => {
    if (en.isIntersecting) navLinks.forEach((a) => a.classList.toggle("is-active", a.getAttribute("href") === `#${en.target.id}`));
  });
}, { rootMargin: "-30% 0px -60% 0px" });
sections.forEach((s) => s && spy.observe(s));

/* --------------------------------------------------------- appearance */
window.AyakaReveal?.sync();
window.addEventListener("motionchange", (e) => {
  const { enabled, systemReduced } = e.detail;
  if (enabled && systemReduced) toast.info("Scroll animations enabled", "Your system has “reduce motion” turned on, so animations stay off until you change it there.");
  else toast.success(enabled ? "Scroll animations enabled" : "Scroll animations turned off", enabled ? "Content animates in as you scroll." : "Pages now show content without motion.");
});

/* ------------------------------------------------------------ general */
const gForm = $("#general-form");
function fillTimezones() {
  const sel = gForm.timezone;
  let zones = [];
  try { zones = Intl.supportedValuesOf("timeZone"); } catch { zones = ["UTC", "Asia/Jakarta", "Asia/Makassar", "Asia/Jayapura", "Asia/Singapore", "Europe/London", "America/New_York"]; }
  if (!zones.includes("UTC")) zones.unshift("UTC");
  if (!zones.includes(settings.timezone)) zones.unshift(settings.timezone);
  sel.innerHTML = zones.map((z) => `<option value="${esc(z)}">${esc(z.replace(/_/g, " "))}</option>`).join("");
}
fillTimezones();
function fillGeneral() {
  gForm.username.value = user.username;
  gForm.email.value = user.email;
  gForm.display_name.value = settings.display_name || "";
  gForm.timezone.value = settings.timezone;
  gForm.date_format.value = settings.date_format;
  $("#email-pw").classList.add("hidden");
  gForm.current_password.value = "";
}
fillGeneral();
const browserTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
$("#detect-tz").addEventListener("click", () => { if (browserTz) { gForm.timezone.value = browserTz; toast.info("Timezone detected", browserTz); } });
gForm.email.addEventListener("input", () => $("#email-pw").classList.toggle("hidden", gForm.email.value.trim().toLowerCase() === user.email));
gForm.date_format.addEventListener("change", () => {
  setPrefs({ date_format: gForm.date_format.value });
  $("#date-preview").textContent = `Preview: ${fmtDate(new Date(), { time: true })}`;
});
$("#date-preview").textContent = `Preview: ${fmtDate(new Date(), { time: true })}`;

gForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearFormErrors(gForm);
  const btn = gForm.querySelector('button[type="submit"]');
  const profile = {};
  const username = gForm.username.value.trim();
  const email = gForm.email.value.trim().toLowerCase();
  if (username !== user.username) profile.username = username;
  if (email !== user.email) {
    profile.email = email;
    if (!gForm.current_password.value) { showFormErrors(gForm, { details: [{ field: "current_password", message: "Enter your password to change email" }] }); return; }
    profile.current_password = gForm.current_password.value;
  }
  if ((gForm.display_name.value.trim()) !== (settings.display_name || "")) profile.display_name = gForm.display_name.value.trim();
  const prefs = { timezone: gForm.timezone.value, date_format: gForm.date_format.value };
  setLoading(btn, true, "Saving…");
  try {
    if (Object.keys(profile).length) {
      const r = await api.patch("/profile", profile);
      Object.assign(user, { username: r.data.username, email: r.data.email });
      settings.display_name = r.data.display_name;
    }
    const s = await api.patch("/settings", prefs);
    settings = { ...settings, ...s.data };
    session.settings = settings;
    setPrefs({ timezone: settings.timezone, date_format: settings.date_format });
    fillGeneral();
    renderSessions();
    toast.success("Settings saved", "Dates and times now use your new preferences.");
  } catch (err) {
    const map = { EMAIL_TAKEN: "email", USERNAME_TAKEN: "username", PERMISSION_DENIED: "current_password" };
    if (map[err.code]) showFormErrors(gForm, { details: [{ field: map[err.code], message: err.message }] });
    else if (!showFormErrors(gForm, err)) toastError(err, "Could not save");
  } finally {
    setLoading(btn, false);
  }
});

/* ----------------------------------------------------------- security */
const pForm = $("#password-form");
const LABELS = ["Too short", "Weak", "Fair", "Good", "Strong"];
pForm.new_password.addEventListener("input", () => {
  const v = pForm.new_password.value;
  const s = passwordScore(v);
  $("#pw-strength").dataset.score = v ? String(Math.max(1, s)) : "0";
  $("#pw-strength-label").textContent = v ? LABELS[s] : "At least 8 characters mixing 2+ of: lowercase, uppercase, digits, symbols.";
});
pForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearFormErrors(pForm);
  const errs = [];
  if (!pForm.current_password.value) errs.push({ field: "current_password", message: "Enter your current password" });
  if (pForm.new_password.value.length < 8) errs.push({ field: "new_password", message: "At least 8 characters" });
  if (pForm.new_password.value !== pForm.confirm_password.value) errs.push({ field: "confirm_password", message: "Passwords do not match" });
  if (errs.length) { showFormErrors(pForm, { details: errs }); return; }
  const btn = pForm.querySelector('button[type="submit"]');
  setLoading(btn, true, "Updating…");
  try {
    const r = await api.post("/profile/change-password", {
      current_password: pForm.current_password.value, new_password: pForm.new_password.value,
      confirm_password: pForm.confirm_password.value, logout_other_sessions: pForm.logout_other_sessions.checked,
    });
    pForm.reset();
    $("#pw-strength").dataset.score = "0";
    toast.success("Password changed", r.data.other_sessions_revoked ? `${r.data.other_sessions_revoked} other session(s) signed out.` : "Your password has been updated.");
    renderSessions();
  } catch (err) {
    if (err.code === "INVALID_CREDENTIALS") showFormErrors(pForm, { details: [{ field: "current_password", message: err.message }] });
    else if (!showFormErrors(pForm, err)) toastError(err, "Could not change password");
  } finally {
    setLoading(btn, false);
  }
});

function describeUA(ua) {
  if (!ua) return { name: "Unknown device", ic: "monitor" };
  const browser = /Edg\//.test(ua) ? "Edge" : /OPR\//.test(ua) ? "Opera" : /Chrome\//.test(ua) ? "Chrome" : /Firefox\//.test(ua) ? "Firefox" : /Safari\//.test(ua) ? "Safari" : /curl|python|httpx|node/i.test(ua) ? ua.split(" ")[0] : "Browser";
  const os = /Windows/.test(ua) ? "Windows" : /Android/.test(ua) ? "Android" : /iPhone|iPad/.test(ua) ? "iOS" : /Mac OS X/.test(ua) ? "macOS" : /Linux/.test(ua) ? "Linux" : "";
  return { name: os ? `${browser} on ${os}` : browser, ic: /Android|iPhone|iPad|Mobile/.test(ua) ? "phone" : "monitor" };
}

async function renderSessions() {
  const el = $("#sessions");
  el.innerHTML = '<div class="skeleton sk-line" style="width:70%"></div>';
  try {
    const r = await api.get("/auth/sessions");
    const others = r.data.filter((s) => !s.current).length;
    $("#logout-others").disabled = others === 0;
    el.innerHTML = r.data.map((s) => {
      const d = describeUA(s.user_agent);
      return `<div class="session-item">
        <span class="si-icon">${icon(d.ic)}</span>
        <div class="si-main"><div class="si-title">${esc(d.name)} ${s.current ? '<span class="badge badge-success" style="margin-left:6px">This device</span>' : ""}</div>
        <div class="si-sub">${esc(s.ip_address || "Unknown IP")} · active ${esc(fmtRelative(s.last_seen_at))} · signed in ${esc(fmtDate(s.created_at))}${s.remember_me ? " · remembered" : ""}</div></div>
        ${s.current ? "" : `<button class="btn btn-sm" data-revoke="${s.id}">Revoke</button>`}
      </div>`;
    }).join("") || emptyState({ title: "No active sessions" });
  } catch (err) {
    el.innerHTML = errorState(err);
  }
}
$("#sessions").addEventListener("click", async (e) => {
  if (e.target.closest("[data-retry]")) return renderSessions();
  const b = e.target.closest("[data-revoke]");
  if (!b) return;
  setLoading(b, true);
  try {
    await api.post(`/auth/sessions/${b.dataset.revoke}/revoke`);
    toast.success("Session revoked", "That device has been signed out.");
    renderSessions();
  } catch (err) { setLoading(b, false); toastError(err); }
});
$("#logout-others").addEventListener("click", async () => {
  const ok = await confirmDialog({ title: "Sign out other sessions?", message: "Every device except this one will be signed out immediately.", confirmText: "Sign out others" });
  if (!ok) return;
  try {
    const r = await api.post("/auth/logout-all");
    toast.success("Signed out", r.message);
    renderSessions();
  } catch (err) { toastError(err); }
});
$("#logout-all").addEventListener("click", async () => {
  const ok = await confirmDialog({ title: "Sign out everywhere?", message: "All sessions, including this one, will be revoked. You'll need to sign in again.", confirmText: "Sign out everywhere", danger: true });
  if (!ok) return;
  try {
    await api.post("/auth/logout-all", undefined, { query: { include_current: true } });
    window.location.href = "login.html?signed_out=1";
  } catch (err) { toastError(err); }
});

/* ----------------------------------------------------- API preferences */
const aForm = $("#api-form");
function fillApi() {
  aForm.default_environment.value = settings.default_environment;
  aForm.default_rate_limit.value = settings.default_rate_limit;
  aForm.default_key_expiration_days.value = String(settings.default_key_expiration_days);
  if (!aForm.default_key_expiration_days.value) aForm.default_key_expiration_days.value = "0";
}
fillApi();
aForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearFormErrors(aForm);
  const rl = Number(aForm.default_rate_limit.value);
  if (!Number.isInteger(rl) || rl < 1 || rl > 10000) { showFormErrors(aForm, { details: [{ field: "default_rate_limit", message: "Whole number between 1 and 10,000" }] }); return; }
  const btn = aForm.querySelector('button[type="submit"]');
  setLoading(btn, true, "Saving…");
  try {
    const r = await api.patch("/settings", {
      default_environment: aForm.default_environment.value, default_rate_limit: rl,
      default_key_expiration_days: Number(aForm.default_key_expiration_days.value),
    });
    settings = { ...settings, ...r.data };
    session.settings = settings;
    toast.success("API preferences saved", "New keys will use these defaults.");
  } catch (err) {
    if (!showFormErrors(aForm, err)) toastError(err, "Could not save");
  } finally { setLoading(btn, false); }
});

/* ------------------------------------------------------- notifications */
for (const input of $$("#notifications input[type=checkbox]")) {
  input.checked = !!settings[input.name];
  input.addEventListener("change", async () => {
    input.disabled = true;
    try {
      const r = await api.patch("/settings", { [input.name]: input.checked });
      settings = { ...settings, ...r.data };
      toast.success("Notification preference saved");
    } catch (err) {
      input.checked = !input.checked;
      toastError(err, "Could not save");
    } finally { input.disabled = false; }
  });
}

/* ---------------------------------------------------------- danger zone */
async function fillKeySelect() {
  const sel = $("#danger-key");
  try {
    const r = await api.get("/keys", { per_page: 100, sort: "name" });
    sel.innerHTML = r.data.length
      ? '<option value="">Select an API key…</option>' + r.data.map((k) => `<option value="${k.id}" data-name="${esc(k.name)}">${esc(k.name)} · ${esc(k.key_prefix)} (${esc(k.status)})</option>`).join("")
      : '<option value="">You have no API keys</option>';
    $("#danger-key-btn").disabled = true;
  } catch (err) {
    sel.innerHTML = `<option value="">${esc(err.message)}</option>`;
  }
}
$("#danger-key").addEventListener("change", (e) => { $("#danger-key-btn").disabled = !e.target.value; });
$("#danger-key-btn").addEventListener("click", async () => {
  const sel = $("#danger-key");
  const name = sel.selectedOptions[0]?.dataset.name;
  const ok = await confirmDialog({ title: "Delete API key?", message: `<strong>${esc(name)}</strong> will be permanently deleted and stop working immediately.`, confirmText: "Delete key", danger: true, requireText: "DELETE" });
  if (!ok) return;
  try {
    await api.del(`/keys/${sel.value}`);
    toast.success("API key deleted", name);
    fillKeySelect();
  } catch (err) { toastError(err); }
});
$("#delete-account").addEventListener("click", async () => {
  const res = await confirmDialog({
    title: "Delete your account?",
    message: `This permanently deletes <strong>${esc(user.username)}</strong> and everything attached to it:
      <ul style="margin:8px 0 0;padding-left:18px;line-height:1.7"><li>All API keys — they stop working immediately</li><li>All usage analytics and activity logs</li><li>Stored records, settings and sessions</li></ul>
      <p style="margin-top:8px">This cannot be undone.</p>`,
    confirmText: "Delete account permanently", danger: true, requireText: "DELETE", requirePassword: true,
  });
  if (!res) return;
  try {
    await api.post("/profile/delete-account", { password: res.password, confirm: "DELETE" });
    window.location.href = "login.html?deleted=1";
  } catch (err) { toastError(err, "Could not delete account"); }
});

renderSessions();
fillKeySelect();
if (location.hash) setTimeout(() => $(location.hash)?.scrollIntoView(), 50);
