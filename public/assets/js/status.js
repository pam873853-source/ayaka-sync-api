/* Public status page: polls the real health endpoints every 30 s (paused while hidden). */
import "./site.js";
import { API_BASE } from "./api.js";
import { $, esc, fmtTime } from "./components.js";

const BADGE = { ok: "badge-success", warn: "badge-warning", down: "badge-error" };

function setRow(svc, state, label, detail) {
  const row = $(`[data-svc="${svc}"]`);
  if (!row) return;
  const badge = row.querySelector(".badge");
  badge.className = `badge badge-dot ${BADGE[state]}`;
  badge.textContent = label;
  if (detail !== undefined) row.querySelector(".hint").textContent = detail;
}

async function getJson(path) {
  const started = performance.now();
  const res = await fetch(`${API_BASE}${path}`, { credentials: "omit", cache: "no-store" });
  const body = await res.json().catch(() => null);
  return { res, body, ms: Math.round(performance.now() - started) };
}

let running = false;
async function check() {
  if (running) return;
  running = true;
  const states = [];
  const help = $("#config-help");
  help.classList.add("hidden");
  try {
    const { res, body, ms } = await getJson("/health");
    if (!res.ok || !body?.success) throw new Error("api");
    setRow("api", "ok", "Operational", `GET /api/v1/health · ${ms} ms`);
    states.push("ok");
    const usage = body.data.usage_logging || {};
    if (usage.failed > 0 && usage.buffered > 0) { setRow("usage", "warn", "Degraded", `${usage.buffered} event(s) buffered, retrying`); states.push("warn"); }
    else { setRow("usage", "ok", "Operational", `${usage.written ?? 0} events written by this instance`); states.push("ok"); }
    const missing = body.data.configuration?.missing || [];
    if (missing.length) {
      setRow("config", "down", "Incomplete", `Missing: ${missing.join(", ")}`);
      states.push("down");
      help.className = "callout callout-warning";
      help.innerHTML = `<strong>Setup required.</strong> Set ${missing.map((m) => `<code>${esc(m)}</code>`).join(", ")} in your environment (Vercel → Project → Settings → Environment Variables) and redeploy. See the README section “Environment variables”.`;
    } else {
      const src = body.data.base_url_source;
      const baseNote = src === "env" ? `Base URL ${body.data.base_url}`
        : `Base URL ${body.data.base_url} (auto-detected — set APP_BASE_URL to pin a custom domain)`;
      setRow("config", "ok", "Configured", `Secrets set · ${baseNote}`);
      states.push("ok");
    }
  } catch {
    setRow("api", "down", "Unreachable", "GET /api/v1/health failed");
    setRow("usage", "down", "Unknown", "API unreachable");
    setRow("config", "down", "Unknown", "API unreachable");
    states.push("down");
  }
  try {
    const { res, body } = await getJson("/health/database");
    if (res.ok && body?.success) { setRow("db", "ok", "Operational", `PostgreSQL · ${body.data.latency_ms} ms query latency`); states.push("ok"); }
    else { setRow("db", "down", body?.error?.code === "DATABASE_NOT_CONFIGURED" ? "Not configured" : "Unavailable", body?.message || `HTTP ${res.status}`); states.push("down"); }
  } catch {
    setRow("db", "down", "Unknown", "Health check failed"); states.push("down");
  }
  const overall = states.includes("down") ? "down" : states.includes("warn") ? "warn" : "ok";
  const text = { ok: "All systems operational", warn: "Partial degradation", down: "Service disruption" }[overall];
  $("#overall").innerHTML = `<span class="status-dot is-${overall}"></span><span>${text}</span>`;
  $("#last-updated").textContent = `Last updated ${fmtTime(new Date())} · refreshes every 30 s.`;
  running = false;
}

let timer = null;
function start() { stop(); check(); timer = setInterval(check, 30000); }
function stop() { if (timer) clearInterval(timer); timer = null; }
document.addEventListener("visibilitychange", () => (document.hidden ? stop() : start()));
$("#refresh").addEventListener("click", check);
start();
