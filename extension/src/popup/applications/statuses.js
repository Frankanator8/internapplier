function populateStatusOptions(statuses, def) {
  if (!Array.isArray(statuses) || !statuses.length) return;
  const current = fStatus.value;
  fStatus.innerHTML = "";
  for (const s of statuses) {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = s;
    fStatus.appendChild(opt);
  }
  if (def) defaultStatus = def;
  if (current && statuses.includes(current)) fStatus.value = current;
  else fStatus.value = defaultStatus;
}

async function loadStatuses() {
  try {
    const cached = await browser.runtime.sendMessage({ type: "GET_STATUSES" });
    if (cached && Array.isArray(cached.statuses)) {
      populateStatusOptions(cached.statuses, cached.default);
    }
  } catch (_) {}
  try {
    const res = await fetch(`${API_BASE}/statuses`, { cache: "no-store" });
    if (res.ok) {
      const data = await res.json();
      populateStatusOptions(data.statuses, data.default);
    }
  } catch (_) {}
}
