/* Shared behaviour for public pages (landing, docs, status, legal, 404). */
import { loadSession } from "./api.js";
import { $, $$, bindCopyButtons, hydrateIcons, icon } from "./components.js";

hydrateIcons();
bindCopyButtons();

const nav = $("#site-nav");
if (nav) {
  const onScroll = () => nav.classList.toggle("is-scrolled", window.scrollY > 8);
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
  const btn = $("#menu-btn");
  const menu = $("#mobile-menu");
  btn?.addEventListener("click", () => {
    const open = menu.classList.toggle("is-open");
    btn.setAttribute("aria-expanded", String(open));
    btn.innerHTML = icon(open ? "x" : "menu");
  });
  $$("#mobile-menu a").forEach((a) => a.addEventListener("click", () => {
    menu.classList.remove("is-open");
    btn.setAttribute("aria-expanded", "false");
    btn.innerHTML = icon("menu");
  }));
}

$$("[data-year]").forEach((el) => { el.textContent = String(new Date().getFullYear()); });
$$("[data-origin]").forEach((el) => { el.textContent = window.location.origin; });

/** Resolves to the session (or null) and swaps guest/member CTAs. */
export const sessionReady = loadSession().catch(() => null).then((s) => {
  $$("[data-guest]").forEach((el) => el.classList.toggle("hidden", !!s));
  $$("[data-member]").forEach((el) => el.classList.toggle("hidden", !s));
  return s;
});
