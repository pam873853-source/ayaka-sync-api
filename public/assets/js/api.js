/* ==========================================================================
   API client — same-origin fetch with HttpOnly cookie sessions.
   * No tokens are stored in localStorage/sessionStorage.
   * CSRF token is kept in memory only (re-fetched from /auth/me on each page load).
   * Expired access tokens are refreshed transparently once (single flight).
   ========================================================================== */
const cfg = window.AYAKA_CONFIG || {};
export const API_ROOT = String(cfg.apiBase || "").replace(/\/$/, "");
export const API_BASE = `${API_ROOT}/api/v1`;

let csrfToken = null;
export const setCsrf = (t) => { csrfToken = t || null; };

export class ApiError extends Error {
  constructor(message, { status = 0, code = "UNKNOWN_ERROR", details = null, headers = null } = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
    this.headers = headers;
  }
}

const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

function buildUrl(path, query) {
  const url = new URL(`${API_BASE}${path}`, window.location.href);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v === undefined || v === null || v === "") continue;
      url.searchParams.set(k, v);
    }
  }
  return url.toString();
}

async function send(method, path, { body, query, signal, raw = false, headers = {} } = {}) {
  const h = { Accept: "application/json", ...headers };
  if (body !== undefined) h["Content-Type"] = "application/json";
  if (UNSAFE.has(method) && csrfToken) h["X-CSRF-Token"] = csrfToken;
  let res;
  try {
    res = await fetch(buildUrl(path, query), {
      method, headers: h, body: body !== undefined ? JSON.stringify(body) : undefined,
      credentials: "include", signal,
    });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new ApiError("Network error. Check your connection and try again.", { code: "NETWORK_ERROR" });
  }
  if (raw && res.ok) return res;
  const type = res.headers.get("content-type") || "";
  let payload = null;
  if (type.includes("application/json")) {
    try { payload = await res.json(); } catch { payload = null; }
  }
  if (!res.ok) {
    const code = payload?.error?.code || (res.status === 429 ? "RATE_LIMIT_EXCEEDED" : "HTTP_" + res.status);
    let message = payload?.message || `Request failed (${res.status})`;
    if (code === "RATE_LIMIT_EXCEEDED" && res.headers.get("Retry-After")) {
      message += ` Retry in ${res.headers.get("Retry-After")}s.`;
    }
    throw new ApiError(message, { status: res.status, code, details: payload?.error?.details, headers: res.headers });
  }
  return payload ?? {};
}

let refreshing = null;
export function refreshSession() {
  if (!refreshing) {
    refreshing = send("POST", "/auth/refresh")
      .then((r) => { setCsrf(r.data?.csrf_token); return r.data; })
      .finally(() => { setTimeout(() => { refreshing = null; }, 0); });
  }
  return refreshing;
}

export async function request(method, path, opts = {}) {
  try {
    return await send(method, path, opts);
  } catch (err) {
    const refreshable = err instanceof ApiError && (err.code === "TOKEN_EXPIRED" || err.code === "AUTHENTICATION_REQUIRED");
    if (refreshable && !opts.noRefresh && !path.startsWith("/auth/refresh")) {
      try {
        await refreshSession();
      } catch {
        const expired = new ApiError("Your session has expired. Please sign in again.", { status: 401, code: "SESSION_EXPIRED" });
        if (!opts.silentExpiry) window.dispatchEvent(new CustomEvent("ayaka:session-expired"));
        throw expired;
      }
      return send(method, path, opts);
    }
    throw err;
  }
}

export const api = {
  get: (p, query, opts) => request("GET", p, { ...opts, query }),
  post: (p, body, opts) => request("POST", p, { ...opts, body }),
  patch: (p, body, opts) => request("PATCH", p, { ...opts, body }),
  del: (p, opts) => request("DELETE", p, opts),
  raw: (p, query) => request("GET", p, { query, raw: true }),
};

/** Returns the session payload or null when signed out. */
export async function loadSession() {
  // Guests have no session-hint cookie: skip the round-trip (and the 401 noise).
  if (!document.cookie.split("; ").some((c) => c === "ayaka_signed_in=1")) return null;
  try {
    const r = await request("GET", "/auth/me", { silentExpiry: true });
    setCsrf(r.data.csrf_token);
    return r.data;
  } catch (err) {
    if (err instanceof ApiError && (err.status === 401 || err.status === 403)) return null;
    throw err;
  }
}
