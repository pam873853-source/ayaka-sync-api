/* Sign in / Register pages */
import { api, ApiError, loadSession, setCsrf } from "./api.js";
import {
  $, bindPasswordToggles, clearFormErrors, debounce, esc, icon, passwordScore, qs, setLoading, showFormErrors, toast,
} from "./components.js";

const mode = document.body.dataset.auth; // "login" | "register"

function safeNext() {
  const n = qs("next");
  // only allow same-site relative page paths
  if (n && /^[a-z0-9_-]+(\.html)?([?#].*)?$/i.test(n)) return n;
  return "dashboard.html";
}

function showAlert(msg, type = "error") {
  const el = $("#form-alert");
  el.className = `callout callout-${type} form-alert is-visible`;
  el.innerHTML = `${icon(type === "error" ? "alertCircle" : type === "success" ? "checkCircle" : "info")}<span>${esc(msg)}</span>`;
}
function hideAlert() { $("#form-alert").className = "callout form-alert"; }

bindPasswordToggles();

// If already signed in, skip the form.
loadSession().then((s) => { if (s) window.location.replace(safeNext()); }).catch(() => {
  showAlert("The server is unreachable right now. Check API status and try again.", "warning");
});

if (qs("signed_out")) setTimeout(() => toast.info("Signed out", "Your session has ended."), 50);
if (qs("deleted")) setTimeout(() => toast.info("Account deleted", "All your data has been removed."), 50);

/* --------------------------------------------------------------- login */
if (mode === "login") {
  const form = $("#login-form");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideAlert();
    clearFormErrors(form);
    const identifier = form.identifier.value.trim();
    const password = form.password.value;
    let bad = false;
    if (identifier.length < 3) { $('[data-error-for="identifier"]').textContent = "Enter your email or username."; form.identifier.classList.add("is-invalid"); bad = true; }
    if (!password) { $('[data-error-for="password"]').textContent = "Enter your password."; form.password.classList.add("is-invalid"); bad = true; }
    if (bad) return;
    const btn = form.querySelector('button[type="submit"]');
    setLoading(btn, true, "Signing in…");
    try {
      const r = await api.post("/auth/login", { identifier, password, remember_me: form.remember_me.checked }, { silentExpiry: true, noRefresh: true });
      setCsrf(r.data.csrf_token);
      window.location.replace(safeNext());
    } catch (err) {
      setLoading(btn, false);
      if (err instanceof ApiError && err.code === "RATE_LIMIT_EXCEEDED") showAlert(err.message, "warning");
      else if (!showFormErrors(form, err)) showAlert(err.message || "Sign in failed");
      form.password.select();
    }
  });
}

/* ------------------------------------------------------------ register */
if (mode === "register") {
  const form = $("#register-form");
  const meter = $("#strength");
  const meterLabel = $("#strength-label");
  const LABELS = ["Too short", "Weak", "Fair", "Good", "Strong"];

  form.password.addEventListener("input", () => {
    const s = passwordScore(form.password.value);
    meter.dataset.score = form.password.value ? String(Math.max(1, s)) : "0";
    meterLabel.textContent = form.password.value ? LABELS[s] : "Use 8+ characters with a mix of letters, numbers & symbols.";
  });

  const checkField = async (field) => {
    const input = form[field];
    const slot = $(`[data-avail-for="${field}"]`);
    const value = input.value.trim();
    const valid = field === "email" ? input.checkValidity() && value.includes("@") : /^[a-zA-Z0-9_.-]{3,32}$/.test(value);
    if (!value || !valid) { slot.textContent = ""; slot.className = "avail"; return; }
    try {
      const r = await api.get("/auth/availability", { [field]: value });
      const ok = r.data[`${field}_available`];
      slot.className = `avail ${ok ? "ok" : "taken"}`;
      slot.innerHTML = ok ? `${icon("check")}Available` : `${icon("x")}${field === "email" ? "Already registered" : "Taken"}`;
    } catch { slot.textContent = ""; }
  };
  // One debouncer per field so typing in one doesn't cancel the other's check.
  const checkUsername = debounce(() => checkField("username"), 450);
  const checkEmail = debounce(() => checkField("email"), 450);
  form.username.addEventListener("input", checkUsername);
  form.email.addEventListener("input", checkEmail);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideAlert();
    clearFormErrors(form);
    const v = {
      username: form.username.value.trim(), email: form.email.value.trim(),
      password: form.password.value, confirm_password: form.confirm_password.value,
    };
    const errs = {};
    if (!/^[a-zA-Z0-9_.-]{3,32}$/.test(v.username)) errs.username = "3–32 characters: letters, digits, '.', '_' or '-'.";
    if (!form.email.checkValidity() || !v.email) errs.email = "Enter a valid email address.";
    if (v.password.length < 8) errs.password = "Password must be at least 8 characters.";
    if (v.confirm_password !== v.password) errs.confirm_password = "Passwords do not match.";
    if (!form.terms.checked) errs.terms = "You need to accept the Terms of Service.";
    if (Object.keys(errs).length) {
      showFormErrors(form, { details: Object.entries(errs).map(([field, message]) => ({ field, message })) });
      return;
    }
    const btn = form.querySelector('button[type="submit"]');
    setLoading(btn, true, "Creating account…");
    try {
      const r = await api.post("/auth/register", v, { silentExpiry: true, noRefresh: true });
      setCsrf(r.data.csrf_token);
      window.location.replace("dashboard.html?welcome=1");
    } catch (err) {
      setLoading(btn, false);
      const map = { EMAIL_TAKEN: "email", USERNAME_TAKEN: "username" };
      if (map[err.code]) showFormErrors(form, { details: [{ field: map[err.code], message: err.message }] });
      else if (!showFormErrors(form, err)) showAlert(err.message || "Registration failed");
    }
  });
}
