/* Profile page */
import { api } from "./api.js";
import { initShell } from "./shell.js";
import { $, clearFormErrors, errorState, fmtDate, fmtNum, initials, setLoading, showFormErrors, toast, toastError } from "./components.js";

await initShell({ page: "profile", crumbs: [{ label: "Profile" }] });

const form = $("#profile-form");

function render(p) {
  const name = p.display_name || p.username;
  $("#p-avatar").textContent = initials(name);
  $("#p-name").textContent = name;
  $("#p-handle").textContent = `@${p.username} · ${p.email}`;
  $("#p-bio").textContent = p.bio || "No bio yet.";
  $("#p-bio").classList.toggle("muted", !p.bio);
  $("#p-keys").textContent = fmtNum(p.stats.api_keys);
  $("#p-reqs").textContent = fmtNum(p.stats.total_requests);
  $("#p-since").textContent = fmtDate(p.created_at);
  $("#p-tz").textContent = p.timezone;
  $("#p-id").textContent = p.id;
  form.display_name.value = p.display_name || "";
  form.bio.value = p.bio || "";
  $("#bio-count").textContent = `${form.bio.value.length}/300`;
}

async function load() {
  try {
    const r = await api.get("/profile");
    render(r.data);
    $("#profile-error").innerHTML = "";
  } catch (err) {
    $("#profile-error").innerHTML = `<div class="card">${errorState(err)}</div>`;
  }
}
$("#profile-error").addEventListener("click", (e) => { if (e.target.closest("[data-retry]")) load(); });
form.bio.addEventListener("input", () => { $("#bio-count").textContent = `${form.bio.value.length}/300`; });
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearFormErrors(form);
  const btn = form.querySelector('button[type="submit"]');
  setLoading(btn, true, "Saving…");
  try {
    const r = await api.patch("/profile", { display_name: form.display_name.value.trim(), bio: form.bio.value.trim() });
    render(r.data);
    toast.success(r.message === "No changes" ? "No changes" : "Profile updated");
  } catch (err) {
    if (!showFormErrors(form, err)) toastError(err, "Could not save profile");
  } finally { setLoading(btn, false); }
});
await load();
