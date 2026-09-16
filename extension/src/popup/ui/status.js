let _healthTimer = null;
let _offlineDelay = 2000;
let _statusBusy = false;

function scheduleHealthCheck(delay) {
  if (_healthTimer) clearTimeout(_healthTimer);
  _healthTimer = setTimeout(() => {
    refreshStatus({ fromPoll: true });
  }, delay);
}

async function refreshStatus({ fromPoll = false, manual = false } = {}) {
  if (_statusBusy && fromPoll) return;
  _statusBusy = true;
  if (manual) _offlineDelay = 2000;
  let ok = false;
  try {
    const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
    ok = res.ok;
  } catch (_) {
    ok = false;
  }
  dot.classList.remove("ok", "err");
  if (statusPill) statusPill.classList.remove("ok", "err");
  if (ok) {
    _offlineDelay = 2000;
    dot.classList.add("ok");
    if (statusPill) statusPill.classList.add("ok");
    statusText.textContent = "Connected";
    if (retryBtn) retryBtn.classList.add("hidden");
    if (offlineHelp) offlineHelp.classList.add("hidden");
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
    scheduleHealthCheck(20000);
  } else {
    dot.classList.add("err");
    if (statusPill) statusPill.classList.add("err");
    statusText.textContent = "Offline";
    if (retryBtn) retryBtn.classList.remove("hidden");
    if (offlineHelp) offlineHelp.classList.remove("hidden");
    loadBtn.disabled = true;
    createBtn.disabled = true;
    askBtn.disabled = true;
    scanBtn.disabled = true;
    loadTarget.innerHTML = "";
    hideResumeChip();
    nameEl.textContent = "";
    profileSection.classList.add("hidden");
    if (autofillControls) autofillControls.classList.add("hidden");
    if (appsEmpty) {
      appsEmpty.classList.remove("hidden");
      appsEmpty.textContent = "Can't reach InternApplier. Start the desktop app, then retry.";
    }
    scheduleHealthCheck(_offlineDelay);
    _offlineDelay = Math.min(_offlineDelay * 2, 10000);
  }
  _statusBusy = false;
}

if (retryBtn) {
  retryBtn.addEventListener("click", () => {
    refreshStatus({ manual: true });
  });
}
