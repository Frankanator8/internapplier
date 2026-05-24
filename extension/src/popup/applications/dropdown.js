function pickBestMatch(apps, meta) {
  if (!Array.isArray(apps) || !apps.length) return "";
  const company = (meta.company || "").toLowerCase().trim();
  const role = (meta.role || "").toLowerCase().trim();
  if (company) {
    for (const a of apps) {
      if ((a.company || "").toLowerCase().trim() === company) return a.uuid;
    }
  }
  if (role) {
    for (const a of apps) {
      if ((a.role || "").toLowerCase().trim() === role) return a.uuid;
    }
  }
  return apps[0].uuid || "";
}

function pickByLink(apps, url) {
  if (!Array.isArray(apps) || !apps.length || !url) return "";
  for (const a of apps) {
    const links = Array.isArray(a.links) ? a.links : [];
    if (links.includes(url)) return a.uuid;
  }
  return "";
}

function selectedApplicationUuid() {
  const v = loadTarget.value;
  if (!v) return null;
  return v;
}

async function populateLoadDropdown() {
  loadTarget.innerHTML = "";
  let meta = {};
  try {
    const reply = await browser.runtime.sendMessage({ type: "EXTRACT_PAGE_META" });
    if (reply && reply.ok) meta = reply.meta || {};
  } catch (_) {}

  let apps = [];
  try {
    const reply = await browser.runtime.sendMessage({ type: "LIST_APPLICATIONS" });
    if (reply && reply.ok && Array.isArray(reply.body)) apps = reply.body;
  } catch (_) {}

  if (!apps.length) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "(no applications)";
    loadTarget.appendChild(opt);
    loadBtn.disabled = true;
    askBtn.disabled = true;
    hideResumeChip();
    return;
  }

  for (const a of apps) {
    const opt = document.createElement("option");
    opt.value = a.uuid || "";
    const company = a.company || "(no company)";
    const role = a.role || "(no role)";
    opt.textContent = `${company} — ${role}`;
    loadTarget.appendChild(opt);
  }

  let best = pickByLink(apps, meta.url);
  if (!best) best = pickBestMatch(apps, meta);
  if (best) loadTarget.value = best;
  loadBtn.disabled = false;
  askBtn.disabled = selectedApplicationUuid() == null;
  refreshResumeChip(selectedApplicationUuid());
}
