/* Runtime configuration for the frontend.
 * apiBase: leave empty when the API is served from the same domain (Vercel default).
 * Set it to e.g. "https://api.your-domain.com" only if the API lives on another origin
 * (then also add the frontend origin to CORS_ORIGINS on the backend). */
window.AYAKA_CONFIG = Object.assign({ apiBase: "" }, window.AYAKA_CONFIG || {});
