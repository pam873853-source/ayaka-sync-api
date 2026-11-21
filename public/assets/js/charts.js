/* Chart.js theme + helpers (monochrome, muted status colours).
   Colours come from CSS custom properties so charts follow the active theme. */
function cssVar(name, fallback) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}
export const C = {
  get white() { return cssVar("--chart-primary", "#f5f5f5"); },
  get secondary() { return cssVar("--chart-secondary", "#d4d4d4"); },
  get fill() { return cssVar("--chart-fill", "#ffffff"); },
  get grey() { return cssVar("--chart-grey", "#707070"); },
  get grid() { return cssVar("--chart-grid", "#1c1c1c"); },
  get tick() { return cssVar("--chart-tick", "#8a8a8a"); },
  get title() { return cssVar("--chart-title", "#5a5a5a"); },
  get success() { return cssVar("--success", "#6fae8a"); },
  get error() { return cssVar("--error", "#d27575"); },
  get warning() { return cssVar("--warning", "#cfa660"); },
  get tooltipBg() { return cssVar("--tooltip-bg", "#f5f5f5"); },
  get tooltipText() { return cssVar("--tooltip-text", "#0a0a0a"); },
};

export function chartsReady() { return typeof window.Chart !== "undefined"; }

export function applyTheme() {
  if (!chartsReady()) return;
  const d = window.Chart.defaults;
  d.color = C.tick;
  d.font.family = '"Geist", "Inter", system-ui, sans-serif';
  d.font.size = 11;
  d.borderColor = C.grid;
  d.animation.duration = 400;
  d.plugins.legend.display = false;
  d.plugins.tooltip.backgroundColor = C.tooltipBg;
  d.plugins.tooltip.titleColor = C.tooltipText;
  d.plugins.tooltip.bodyColor = C.tooltipText;
  d.plugins.tooltip.borderWidth = 0;
  d.plugins.tooltip.padding = 10;
  d.plugins.tooltip.cornerRadius = 6;
  d.plugins.tooltip.displayColors = true;
  d.plugins.tooltip.boxPadding = 4;
  d.maintainAspectRatio = false;
  d.responsive = true;
}

export function axes({ stacked = false, yTitle = "", suggestedMax } = {}) {
  return {
    x: { stacked, grid: { display: false }, ticks: { maxRotation: 0, autoSkipPadding: 16 }, border: { color: C.grid } },
    y: {
      stacked, beginAtZero: true, suggestedMax, grid: { color: C.grid }, border: { display: false },
      ticks: { precision: 0, padding: 8 }, title: yTitle ? { display: true, text: yTitle, color: C.title } : undefined,
    },
  };
}

/** Create or update a chart in place. */
export function upsertChart(store, key, canvas, config) {
  if (!chartsReady() || !canvas) return null;
  const existing = store[key];
  if (existing && existing.config.type === config.type) {
    existing.data.labels = config.data.labels;
    config.data.datasets.forEach((ds, i) => {
      if (existing.data.datasets[i]) Object.assign(existing.data.datasets[i], ds);
      else existing.data.datasets.push(ds);
    });
    existing.data.datasets.length = config.data.datasets.length;
    if (config.options) existing.options = config.options;
    existing.update();
    return existing;
  }
  existing?.destroy();
  store[key] = new window.Chart(canvas, config);
  return store[key];
}

export function lineGradient(ctx, color) {
  const g = ctx.createLinearGradient(0, 0, 0, ctx.canvas.clientHeight || 260);
  g.addColorStop(0, color + "33");
  g.addColorStop(1, color + "00");
  return g;
}

/** Re-render charts when the user switches dark/light mode. */
export function onThemeChange(rerender) {
  window.addEventListener("themechange", () => { applyTheme(); rerender(); });
}
