async function refreshStatus() {
  let ok = false;
  try {
    const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
    ok = res.ok;
  } catch (_) {
    ok = false;
  }
  dot.classList.remove("ok", "err");
  if (ok) {
    dot.classList.add("ok");
    statusText.textContent = "Connected to localhost:8765";
    createBtn.disabled = false;
    scanBtn.disabled = false;
    try {
      const res = await fetch(`${API_BASE}/profile/general_info`);
      const info = await res.json();
      const name = [info.first_name, info.last_name].filter(Boolean).join(" ");
      nameEl.textContent = name ? `Profile: ${name}` : "Profile loaded (no name)";
    } catch (_) {
      nameEl.textContent = "";
    }
    await populateLoadDropdown();
    renderProfilePanel().catch(() => {});
  } else {
    dot.classList.add("err");
    statusText.textContent = "Server unreachable";
    loadBtn.disabled = true;
    createBtn.disabled = true;
    askBtn.disabled = true;
    scanBtn.disabled = true;
    loadTarget.innerHTML = "";
    hideResumeChip();
    nameEl.textContent = "";
    profileSection.classList.add("hidden");
  }
}
