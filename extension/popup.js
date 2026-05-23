const dot = document.getElementById("dot");
const statusText = document.getElementById("status-text");
const nameEl = document.getElementById("name");
const loadTarget = document.getElementById("load-target");
const resumeChipRow = document.getElementById("resume-chip-row");
const resumeChip = document.getElementById("resume-chip");
const resumeChipName = document.getElementById("resume-chip-name");
const resumeGenerateBtn = document.getElementById("resume-generate-btn");
const loadBtn = document.getElementById("load-btn");
const createBtn = document.getElementById("create-btn");
const askBtn = document.getElementById("ask-btn");
const resultEl = document.getElementById("result");
const profileSection = document.getElementById("profile-section");
const profileTree = document.getElementById("profile-tree");
const profileSearch = document.getElementById("profile-search");
const profileEmpty = document.getElementById("profile-empty");
const answersSection = document.getElementById("answers-section");
const answersList = document.getElementById("answers-list");

const scanBtn = document.getElementById("scan-btn");
const scanView = document.getElementById("scan-view");
const scanSummary = document.getElementById("scan-summary");
const scanList = document.getElementById("scan-list");
const scanBack = document.getElementById("scan-back");
const scanAdd = document.getElementById("scan-add");
const scanSelectNew = document.getElementById("scan-select-new");
const scanDeselect = document.getElementById("scan-deselect");
const scanResult = document.getElementById("scan-result");
const scanPick = document.getElementById("scan-pick");
const scanScope = document.getElementById("scan-scope");
const scanScopeSelector = document.getElementById("scan-scope-selector");
const scanScopeClear = document.getElementById("scan-scope-clear");

const mainView = document.getElementById("main-view");
const formView = document.getElementById("form-view");
const fCompany = document.getElementById("f-company");
const fRole = document.getElementById("f-role");
const fDate = document.getElementById("f-date");
const fLink = document.getElementById("f-link");
const fStatus = document.getElementById("f-status");
const fNotes = document.getElementById("f-notes");
const fDescription = document.getElementById("f-description");
const saveBtn = document.getElementById("save-btn");
const cancelBtn = document.getElementById("cancel-btn");
const formResult = document.getElementById("form-result");

const API_BASE = "http://127.0.0.1:8765";
const PICKED_KEY = "picked";
const DRAFT_KEY = "application_draft";

const systemDarkMQ = window.matchMedia("(prefers-color-scheme: dark)");
let themePreference = "system";

function applyThemeFromPreference() {
  const effective =
    themePreference === "dark" ||
    (themePreference === "system" && systemDarkMQ.matches);
  document.body.classList.toggle("dark", effective);
}

function applyTheme(pref) {
  themePreference = pref === "light" || pref === "dark" ? pref : "system";
  applyThemeFromPreference();
}

systemDarkMQ.addEventListener("change", () => {
  if (themePreference === "system") applyThemeFromPreference();
});

async function loadTheme() {
  try {
    const res = await fetch(`${API_BASE}/theme`, { cache: "no-store" });
    if (res.ok) {
      const data = await res.json();
      applyTheme(data && data.preference);
      return;
    }
  } catch (_) {}
  applyTheme("system");
}

applyTheme("system");

const FIELD_TO_INPUT = {
  company: fCompany,
  role: fRole,
  date: fDate,
  link: fLink,
  notes: fNotes,
  description: fDescription,
};

let defaultStatus = "Added";

function todayISO() {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

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

let _resumeChipObjectUrl = null;
let _resumePollTimer = null;
let _resumePollUuid = null;

function hideResumeChip() {
  if (resumeChip) {
    resumeChip._file = null;
    resumeChip.hidden = true;
  }
  if (resumeGenerateBtn) resumeGenerateBtn.hidden = true;
  if (resumeChipRow) resumeChipRow.hidden = true;
  if (_resumeChipObjectUrl) {
    try { URL.revokeObjectURL(_resumeChipObjectUrl); } catch (_) {}
    _resumeChipObjectUrl = null;
  }
}

function stopResumePolling() {
  if (_resumePollTimer) {
    clearTimeout(_resumePollTimer);
    _resumePollTimer = null;
  }
  _resumePollUuid = null;
}

function showResumeGenerateButton(uuid, { generating = false } = {}) {
  if (!resumeGenerateBtn || !resumeChipRow) return;
  if (resumeChip) {
    resumeChip._file = null;
    resumeChip.hidden = true;
  }
  resumeGenerateBtn.hidden = false;
  resumeGenerateBtn.disabled = generating;
  resumeGenerateBtn.textContent = generating ? "Generating…" : "Generate Resume";
  resumeGenerateBtn.dataset.uuid = uuid;
  resumeChipRow.hidden = false;
}

async function refreshResumeChip(uuid) {
  if (!resumeChip || !resumeChipRow) return;
  if (_resumePollUuid && _resumePollUuid !== uuid) stopResumePolling();
  if (!uuid) {
    stopResumePolling();
    hideResumeChip();
    return;
  }
  let reply = null;
  try {
    reply = await browser.runtime.sendMessage({
      type: "FETCH_RESUME",
      uuid,
    });
  } catch (_) {}
  if (loadTarget.value !== uuid) return;
  if (reply && reply.ok && reply.arrayBuffer) {
    if (_resumePollUuid === uuid) stopResumePolling();
    const file = new File([reply.arrayBuffer], reply.filename || "Resume.pdf", {
      type: "application/pdf",
    });
    resumeChip._file = file;
    resumeChip.hidden = false;
    if (resumeChipName) resumeChipName.textContent = file.name;
    if (resumeGenerateBtn) resumeGenerateBtn.hidden = true;
    resumeChipRow.hidden = false;
    return;
  }
  if (reply && reply.status === 404) {
    // No resume yet. If a job is already running for this uuid, keep polling
    // and show the disabled button; otherwise show the actionable button.
    let statusReply = null;
    try {
      statusReply = await browser.runtime.sendMessage({
        type: "GENERATE_RESUME_STATUS",
        uuid,
      });
    } catch (_) {}
    if (loadTarget.value !== uuid) return;
    const running = statusReply && statusReply.ok && statusReply.body
      && statusReply.body.status === "running";
    showResumeGenerateButton(uuid, { generating: !!running });
    if (running) startResumePolling(uuid);
    return;
  }
  hideResumeChip();
}

function startResumePolling(uuid) {
  stopResumePolling();
  _resumePollUuid = uuid;
  const tick = async () => {
    if (_resumePollUuid !== uuid || loadTarget.value !== uuid) {
      stopResumePolling();
      return;
    }
    let reply = null;
    try {
      reply = await browser.runtime.sendMessage({
        type: "GENERATE_RESUME_STATUS",
        uuid,
      });
    } catch (_) {}
    if (_resumePollUuid !== uuid || loadTarget.value !== uuid) return;
    const body = reply && reply.ok ? reply.body : null;
    if (body && body.status === "done") {
      stopResumePolling();
      refreshResumeChip(uuid);
    } else if (body && body.status === "error") {
      stopResumePolling();
      showResumeGenerateButton(uuid, { generating: false });
      if (resultEl) resultEl.textContent = `Resume generation failed: ${body.error || "unknown error"}`;
    } else {
      _resumePollTimer = setTimeout(tick, 3000);
    }
  };
  _resumePollTimer = setTimeout(tick, 3000);
}

if (resumeGenerateBtn) {
  resumeGenerateBtn.addEventListener("click", async () => {
    const uuid = resumeGenerateBtn.dataset.uuid;
    if (!uuid || loadTarget.value !== uuid) return;
    showResumeGenerateButton(uuid, { generating: true });
    if (resultEl) resultEl.textContent = "";
    let reply = null;
    try {
      reply = await browser.runtime.sendMessage({
        type: "GENERATE_RESUME",
        uuid,
      });
    } catch (_) {}
    if (loadTarget.value !== uuid) return;
    if (reply && reply.ok) {
      startResumePolling(uuid);
      return;
    }
    const detail = (reply && reply.body && reply.body.detail)
      || (reply && reply.error)
      || (reply && reply.status ? `HTTP ${reply.status}` : "unknown error");
    showResumeGenerateButton(uuid, { generating: false });
    if (resultEl) resultEl.textContent = `Could not start resume generation: ${detail}`;
  });
}

if (resumeChip) {
  resumeChip.addEventListener("dragstart", (e) => {
    const file = resumeChip._file;
    if (!file) { e.preventDefault(); return; }
    try {
      e.dataTransfer.effectAllowed = "copy";
      e.dataTransfer.items.add(file);
      if (_resumeChipObjectUrl) {
        try { URL.revokeObjectURL(_resumeChipObjectUrl); } catch (_) {}
      }
      _resumeChipObjectUrl = URL.createObjectURL(file);
      e.dataTransfer.setData(
        "DownloadURL",
        `application/pdf:${file.name}:${_resumeChipObjectUrl}`
      );
    } catch (_) {
      // Some browsers throw on items.add for cross-origin; fall through silently.
    }
  });
}

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

loadTarget.addEventListener("change", () => {
  askBtn.disabled = selectedApplicationUuid() == null;
  refreshResumeChip(selectedApplicationUuid());
});

loadBtn.addEventListener("click", async () => {
  const uuid = loadTarget.value;
  if (!uuid) {
    resultEl.textContent = "Pick an application.";
    return;
  }
  resultEl.textContent = "Loading…";
  loadBtn.disabled = true;
  try {
    const reply = await browser.runtime.sendMessage({
      type: "AUTOFILL_WITH_APPLICATION",
      uuid,
    });
    if (reply && reply.ok) {
      resultEl.textContent = "Done.";
    } else {
      const detail = reply && (reply.error || reply.reason || `HTTP ${reply.status}`);
      resultEl.textContent = `Could not autofill: ${detail || "unknown error"}`;
    }
  } catch (e) {
    resultEl.textContent = `Error: ${e.message}`;
  } finally {
    loadBtn.disabled = false;
  }
});

function showForm() {
  mainView.classList.add("hidden");
  scanView.classList.add("hidden");
  formView.classList.remove("hidden");
}

function showMain() {
  formView.classList.add("hidden");
  scanView.classList.add("hidden");
  mainView.classList.remove("hidden");
}

function showScan() {
  formView.classList.add("hidden");
  mainView.classList.add("hidden");
  scanView.classList.remove("hidden");
}

function normText(s) {
  return (s || "").toString().toLowerCase().replace(/\s+/g, " ").trim();
}

let _scanState = { jobs: [], duplicates: [], selector: null };

function updateScanScopeIndicator() {
  if (_scanState.selector) {
    scanScopeSelector.textContent = _scanState.selector;
    scanScope.classList.remove("hidden");
  } else {
    scanScope.classList.add("hidden");
  }
}

async function markDuplicatesAndRender(jobs) {
  let apps = [];
  try {
    const reply = await browser.runtime.sendMessage({ type: "LIST_APPLICATIONS" });
    if (reply && reply.ok && Array.isArray(reply.body)) apps = reply.body;
  } catch (_) {}
  const duplicates = jobs.map((j) => isDuplicate(j, apps));
  const newCount = duplicates.filter((d) => !d).length;
  _scanState.jobs = jobs;
  _scanState.duplicates = duplicates;
  scanSummary.textContent = `Found ${jobs.length} posting${jobs.length === 1 ? "" : "s"}, ${newCount} new.`;
  renderScanList();
}

function isDuplicate(job, apps) {
  const link = (job.link || "").trim();
  const company = normText(job.company);
  const role = normText(job.role);
  for (const a of apps) {
    const links = Array.isArray(a.links) ? a.links : [];
    if (link && links.includes(link)) return true;
    if (company && role && normText(a.company) === company && normText(a.role) === role) return true;
  }
  return false;
}

function renderScanList() {
  scanList.innerHTML = "";
  if (!_scanState.jobs.length) {
    const empty = document.createElement("div");
    empty.style.padding = "8px";
    empty.style.color = "#6b7280";
    empty.textContent = "No postings detected on this page.";
    scanList.appendChild(empty);
    return;
  }
  _scanState.jobs.forEach((job, i) => {
    const dup = _scanState.duplicates[i];
    const row = document.createElement("label");
    row.className = "scan-row" + (dup ? " dup" : "");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = !dup;
    cb.dataset.idx = String(i);
    const main = document.createElement("div");
    main.className = "scan-main";
    const title = document.createElement("div");
    title.className = "scan-title";
    const company = job.company || "(no company)";
    const role = job.role || "(no role)";
    title.textContent = `${company} — ${role}`;
    title.title = title.textContent;
    main.appendChild(title);
    let subText = "";
    try { subText = job.link ? new URL(job.link).host : ""; } catch (_) { subText = job.link || ""; }
    if (job.location) subText = subText ? `${subText} · ${job.location}` : job.location;
    if (subText) {
      const sub = document.createElement("div");
      sub.className = "scan-sub";
      sub.textContent = subText;
      sub.title = subText;
      main.appendChild(sub);
    }
    row.appendChild(cb);
    row.appendChild(main);
    if (dup) {
      const badge = document.createElement("span");
      badge.className = "badge";
      badge.textContent = "already added";
      row.appendChild(badge);
    }
    scanList.appendChild(row);
  });
}

async function runScan(selector) {
  showScan();
  scanResult.textContent = "";
  scanSummary.textContent = selector ? "Scanning section…" : "Scanning page…";
  scanList.innerHTML = "";
  _scanState.selector = selector || null;
  updateScanScopeIndicator();
  let jobs = [];
  try {
    const reply = await browser.runtime.sendMessage({
      type: "EXTRACT_JOB_LIST",
      selector: selector || null,
    });
    if (reply && reply.ok) jobs = reply.jobs || [];
    else scanResult.textContent = `Scan error: ${(reply && reply.reason) || "unknown"}`;
  } catch (e) {
    scanResult.textContent = `Error: ${e.message}`;
  }
  await markDuplicatesAndRender(jobs);
}

scanBtn.addEventListener("click", () => {
  runScan().catch((e) => { scanResult.textContent = `Error: ${e.message}`; });
});

scanBack.addEventListener("click", () => {
  showMain();
});

scanPick.addEventListener("click", async () => {
  scanResult.textContent = "Click an element on the page to scope the scan (Esc to cancel)…";
  try {
    await browser.runtime.sendMessage({ type: "START_PICKER", field: "scan_container" });
  } catch (e) {
    scanResult.textContent = `Error: ${e.message}`;
  }
});

scanScopeClear.addEventListener("click", () => {
  runScan(null).catch((e) => { scanResult.textContent = `Error: ${e.message}`; });
});

scanSelectNew.addEventListener("click", () => {
  scanList.querySelectorAll("input[type=checkbox]").forEach((cb) => {
    const idx = parseInt(cb.dataset.idx, 10);
    cb.checked = !_scanState.duplicates[idx];
  });
});

scanDeselect.addEventListener("click", () => {
  scanList.querySelectorAll("input[type=checkbox]").forEach((cb) => { cb.checked = false; });
});

scanAdd.addEventListener("click", async () => {
  const selected = [];
  scanList.querySelectorAll("input[type=checkbox]").forEach((cb) => {
    if (cb.checked) {
      const idx = parseInt(cb.dataset.idx, 10);
      const job = _scanState.jobs[idx];
      if (!job) return;
      selected.push({
        company: job.company || "",
        role: job.role || "",
        date: todayISO(),
        links: job.link ? [job.link] : [],
        status: defaultStatus,
        notes: job.location ? `Location: ${job.location}` : "",
        description: "",
      });
    }
  });
  if (!selected.length) {
    scanResult.textContent = "Nothing selected.";
    return;
  }
  scanAdd.disabled = true;
  scanResult.textContent = `Adding ${selected.length}…`;
  try {
    const reply = await browser.runtime.sendMessage({
      type: "BULK_CREATE_APPLICATIONS",
      entries: selected,
    });
    if (reply && reply.ok) {
      const added = (reply.body && reply.body.added) || selected.length;
      scanResult.textContent = `Added ${added} application${added === 1 ? "" : "s"}.`;
      await populateLoadDropdown();
      const apps = (await browser.runtime.sendMessage({ type: "LIST_APPLICATIONS" })) || {};
      const list = (apps.ok && Array.isArray(apps.body)) ? apps.body : [];
      _scanState.duplicates = _scanState.jobs.map((j) => isDuplicate(j, list));
      renderScanList();
    } else {
      const detail = reply && (reply.error || (reply.body && JSON.stringify(reply.body)) || `HTTP ${reply.status}`);
      scanResult.textContent = `Add failed: ${detail || "unknown error"}`;
    }
  } catch (e) {
    scanResult.textContent = `Error: ${e.message}`;
  } finally {
    scanAdd.disabled = false;
  }
});

function readForm() {
  return {
    company: fCompany.value.trim(),
    role: fRole.value.trim(),
    date: fDate.value.trim(),
    link: fLink.value.trim(),
    status: fStatus.value,
    notes: fNotes.value.trim(),
    description: fDescription.value.trim(),
  };
}

function writeForm(data) {
  fCompany.value = data.company || "";
  fRole.value = data.role || "";
  fDate.value = data.date || todayISO();
  fLink.value = data.link || "";
  if (data.status) fStatus.value = data.status;
  else fStatus.value = defaultStatus;
  fNotes.value = data.notes || "";
  fDescription.value = data.description || "";
}

async function saveDraft() {
  try {
    await browser.storage.local.set({ [DRAFT_KEY]: readForm() });
  } catch (_) {}
}

function applyPicked(picked) {
  if (!picked || !picked.field) return;
  const input = FIELD_TO_INPUT[picked.field];
  if (!input) return;
  input.value = picked.value || "";
  input.dispatchEvent(new Event("input", { bubbles: true }));
  saveDraft();
  formResult.textContent = `Picked ${picked.field}.`;
}

async function loadDraftOrExtract() {
  const stored = await browser.storage.local.get([DRAFT_KEY, PICKED_KEY]);
  const draft = stored[DRAFT_KEY];
  const picked = stored[PICKED_KEY];
  if (draft) {
    writeForm(draft);
    if (picked) {
      applyPicked(picked);
      await browser.storage.local.remove(PICKED_KEY);
    }
    showForm();
    return;
  }
  formResult.textContent = "Reading page…";
  let meta = {};
  try {
    const reply = await browser.runtime.sendMessage({ type: "EXTRACT_PAGE_META" });
    if (reply && reply.ok) meta = reply.meta || {};
  } catch (_) {}
  writeForm({
    company: meta.company || "",
    role: meta.role || "",
    date: todayISO(),
    link: meta.url || "",
    status: defaultStatus,
    notes: "",
    description: meta.description || "",
  });
  formResult.textContent = "";
  await saveDraft();
  showForm();
}

createBtn.addEventListener("click", () => {
  loadDraftOrExtract().catch((e) => {
    resultEl.textContent = `Error: ${e.message}`;
  });
});

document.querySelectorAll(".pick-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const field = btn.getAttribute("data-pick-field") || "description";
    await saveDraft();
    try {
      await browser.runtime.sendMessage({ type: "START_PICKER", field });
      formResult.textContent = `Click an element on the page to set ${field} (Esc to cancel).`;
    } catch (e) {
      formResult.textContent = `Error: ${e.message}`;
    }
  });
});

cancelBtn.addEventListener("click", async () => {
  await browser.storage.local.remove([DRAFT_KEY, PICKED_KEY]);
  formResult.textContent = "";
  showMain();
});

saveBtn.addEventListener("click", async () => {
  const entry = readForm();
  if (!entry.company && !entry.role) {
    formResult.textContent = "Company or Role required.";
    return;
  }
  saveBtn.disabled = true;
  formResult.textContent = "Saving…";
  const payload = { ...entry };
  const linkVal = (payload.link || "").trim();
  delete payload.link;
  payload.links = linkVal ? [linkVal] : [];
  try {
    const reply = await browser.runtime.sendMessage({
      type: "CREATE_APPLICATION",
      entry: payload,
    });
    if (reply && reply.ok) {
      await browser.storage.local.remove([DRAFT_KEY, PICKED_KEY]);
      formResult.textContent = "";
      resultEl.textContent = "Application saved.";
      showMain();
      await populateLoadDropdown();
    } else {
      const detail = reply && (reply.error || (reply.body && JSON.stringify(reply.body)) || `HTTP ${reply.status}`);
      formResult.textContent = `Save failed: ${detail || "unknown error"}`;
    }
  } catch (e) {
    formResult.textContent = `Error: ${e.message}`;
  } finally {
    saveBtn.disabled = false;
  }
});

[fCompany, fRole, fDate, fLink, fStatus, fNotes, fDescription].forEach((el) => {
  el.addEventListener("input", saveDraft);
  el.addEventListener("change", saveDraft);
});

function makeChip(value, label) {
  const text = String(value == null ? "" : value);
  if (!text.trim()) return null;
  const chip = document.createElement("span");
  chip.className = "chip";
  chip.setAttribute("draggable", "true");
  const preview = text.length > 60 ? text.slice(0, 57) + "…" : text;
  if (label) {
    const lbl = document.createElement("span");
    lbl.className = "chip-label";
    lbl.textContent = label + ":";
    chip.appendChild(lbl);
  }
  chip.appendChild(document.createTextNode(preview));
  chip.title = text;
  chip.addEventListener("dragstart", (e) => {
    e.dataTransfer.setData("text/plain", text);
    e.dataTransfer.effectAllowed = "copy";
  });
  return chip;
}

function appendChipRow(container, fieldName, value) {
  if (value == null || String(value).trim() === "") return;
  const chip = makeChip(value);
  if (!chip) return;
  const row = document.createElement("div");
  row.className = "chip-row";
  const name = document.createElement("span");
  name.className = "field-name";
  name.textContent = fieldName;
  row.appendChild(name);
  row.appendChild(chip);
  container.appendChild(row);
}

function makeTreeNode(title, openByDefault) {
  const d = document.createElement("details");
  d.className = "tree";
  if (openByDefault) d.open = true;
  d.dataset.defaultOpen = openByDefault ? "1" : "0";
  const s = document.createElement("summary");
  s.textContent = title;
  d.appendChild(s);
  const body = document.createElement("div");
  body.className = "tree-body";
  d.appendChild(body);
  return { details: d, body };
}

function renderDict(container, obj) {
  if (!obj || typeof obj !== "object") return;
  for (const [k, v] of Object.entries(obj)) {
    if (v == null) continue;
    if (typeof v === "object") {
      if (Array.isArray(v)) {
        if (!v.length) continue;
        const node = makeTreeNode(k, false);
        for (let i = 0; i < v.length; i++) {
          const item = v[i];
          if (item && typeof item === "object" && !Array.isArray(item)) {
            const inner = makeTreeNode(`#${i + 1}`, false);
            renderDict(inner.body, item);
            node.body.appendChild(inner.details);
          } else if (Array.isArray(item)) {
            const inner = makeTreeNode(`#${i + 1}`, false);
            for (let j = 0; j < item.length; j++) appendChipRow(inner.body, String(j + 1), item[j]);
            node.body.appendChild(inner.details);
          } else {
            appendChipRow(node.body, String(i + 1), item);
          }
        }
        container.appendChild(node.details);
      } else {
        const node = makeTreeNode(k, false);
        renderDict(node.body, v);
        container.appendChild(node.details);
      }
    } else {
      appendChipRow(container, k, v);
    }
  }
}

async function renderProfilePanel() {
  profileTree.innerHTML = "";
  let profile = null;
  try {
    profile = await browser.runtime.sendMessage({ type: "GET_PROFILE" });
  } catch (_) {}
  if (!profile || typeof profile !== "object") {
    profileSection.classList.add("hidden");
    return;
  }
  const order = ["general_info", "experience", "projects", "skills", "applications"];
  const seen = new Set();
  for (const key of order) {
    if (!(key in profile)) continue;
    seen.add(key);
    const v = profile[key];
    if (v == null) continue;
    if (typeof v === "object") {
      const node = makeTreeNode(key, key === "general_info");
      if (Array.isArray(v)) {
        if (!v.length) continue;
        for (let i = 0; i < v.length; i++) {
          const item = v[i];
          const title = (item && (item.company || item.role || item.name || item.title)) || `#${i + 1}`;
          if (item && typeof item === "object" && !Array.isArray(item)) {
            const inner = makeTreeNode(String(title), false);
            renderDict(inner.body, item);
            node.body.appendChild(inner.details);
          } else {
            appendChipRow(node.body, String(i + 1), item);
          }
        }
      } else {
        renderDict(node.body, v);
      }
      profileTree.appendChild(node.details);
    } else {
      appendChipRow(profileTree, key, v);
    }
  }
  for (const [k, v] of Object.entries(profile)) {
    if (seen.has(k)) continue;
    if (v == null) continue;
    if (typeof v === "object") {
      const node = makeTreeNode(k, false);
      renderDict(node.body, v);
      profileTree.appendChild(node.details);
    } else {
      appendChipRow(profileTree, k, v);
    }
  }
  profileSection.classList.remove("hidden");
  applyProfileFilter();
}

function applyProfileFilter() {
  const query = (profileSearch.value || "").toLowerCase().trim();
  const rows = profileTree.querySelectorAll(".chip-row");
  rows.forEach((row) => {
    if (!query) {
      row.style.display = "";
      return;
    }
    const fieldName = row.querySelector(".field-name");
    const chip = row.querySelector(".chip");
    const hay = [
      fieldName ? fieldName.textContent : "",
      chip ? chip.textContent : "",
      chip ? chip.title : "",
    ].join(" ").toLowerCase();
    row.style.display = hay.includes(query) ? "" : "none";
  });

  const allDetails = Array.from(profileTree.querySelectorAll("details.tree"));
  const summaryMatches = new Set();
  if (query) {
    for (const d of allDetails) {
      const s = d.querySelector(":scope > summary");
      if (s && s.textContent.toLowerCase().includes(query)) {
        summaryMatches.add(d);
        d.querySelectorAll(".chip-row").forEach((r) => { r.style.display = ""; });
      }
    }
  }

  for (let i = allDetails.length - 1; i >= 0; i--) {
    const d = allDetails[i];
    if (!query) {
      d.style.display = "";
      d.open = d.dataset.defaultOpen === "1";
      continue;
    }
    const hasVisibleRow = Array.from(d.querySelectorAll(".chip-row"))
      .some((r) => r.style.display !== "none");
    const hasVisibleChild = Array.from(d.querySelectorAll(":scope > .tree-body > details.tree"))
      .some((c) => c.style.display !== "none");
    const visible = summaryMatches.has(d) || hasVisibleRow || hasVisibleChild;
    d.style.display = visible ? "" : "none";
    d.open = visible;
  }

  const visibleRows = Array.from(rows).some((r) => r.style.display !== "none");
  const visibleDetails = allDetails.some((d) => d.style.display !== "none");
  profileEmpty.classList.toggle("hidden", !query || visibleRows || visibleDetails);
}

profileSearch.addEventListener("input", applyProfileFilter);

function selectedApplicationUuid() {
  const v = loadTarget.value;
  if (!v) return null;
  return v;
}

let _answerCounter = 0;

function renderAnswerCard(question) {
  answersSection.classList.remove("hidden");
  const id = `answer-${++_answerCounter}`;
  const card = document.createElement("div");
  card.className = "answer-card";
  card.id = id;
  const q = document.createElement("div");
  q.className = "question";
  q.textContent = question.length > 200 ? question.slice(0, 197) + "…" : question;
  q.title = question;
  card.appendChild(q);
  const body = document.createElement("div");
  body.className = "spinner";
  body.textContent = "Thinking…";
  card.appendChild(body);
  answersList.insertBefore(card, answersList.firstChild);
  return { card, body };
}

function finalizeAnswerCard(card, body, answer) {
  body.className = "answer-text";
  body.textContent = answer;
  body.setAttribute("draggable", "true");
  body.addEventListener("dragstart", (e) => {
    e.dataTransfer.setData("text/plain", answer);
    e.dataTransfer.effectAllowed = "copy";
  });
  const actions = document.createElement("div");
  actions.className = "answer-actions";
  const copyBtn = document.createElement("button");
  copyBtn.className = "secondary";
  copyBtn.textContent = "Copy";
  copyBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(answer);
      copyBtn.textContent = "Copied!";
      setTimeout(() => { copyBtn.textContent = "Copy"; }, 1200);
    } catch (_) {}
  });
  const dismissBtn = document.createElement("button");
  dismissBtn.className = "secondary";
  dismissBtn.textContent = "×";
  dismissBtn.title = "Dismiss";
  dismissBtn.style.flex = "0";
  dismissBtn.addEventListener("click", () => {
    card.remove();
    if (!answersList.children.length) answersSection.classList.add("hidden");
  });
  actions.appendChild(copyBtn);
  actions.appendChild(dismissBtn);
  card.appendChild(actions);
}

function failAnswerCard(card, body, error) {
  body.className = "answer-text";
  body.style.color = "#b91c1c";
  body.textContent = `Failed: ${error || "unknown error"}`;
}

async function askQuestion(question) {
  const trimmed = (question || "").replace(/\s+/g, " ").trim();
  if (!trimmed) {
    resultEl.textContent = "No question text picked.";
    return;
  }
  const { card, body } = renderAnswerCard(trimmed);
  const appUuid = selectedApplicationUuid();
  try {
    const reply = await browser.runtime.sendMessage({
      type: "ANSWER_QUESTION",
      question: trimmed,
      application_uuid: appUuid,
    });
    if (reply && reply.ok && reply.answer) {
      finalizeAnswerCard(card, body, reply.answer);
      resultEl.textContent = "Answer ready — copied to clipboard.";
      try { await navigator.clipboard.writeText(reply.answer); } catch (_) {}
    } else {
      failAnswerCard(card, body, (reply && reply.error) || "no answer");
      resultEl.textContent = "AI answer failed.";
    }
  } catch (e) {
    failAnswerCard(card, body, e.message);
  }
}

askBtn.addEventListener("click", async () => {
  resultEl.textContent = "Click a question on the page (Esc to cancel)…";
  try {
    await browser.runtime.sendMessage({ type: "START_PICKER", field: "question" });
  } catch (e) {
    resultEl.textContent = `Error: ${e.message}`;
  }
});

browser.runtime.onMessage.addListener((msg) => {
  if (msg && msg.type === "PICKED" && msg.picked) {
    if (msg.picked.field === "question") {
      browser.storage.local.remove(PICKED_KEY).catch(() => {});
      askQuestion(msg.picked.value);
      return;
    }
    applyPicked(msg.picked);
    browser.storage.local.remove(PICKED_KEY).catch(() => {});
  }
  if (msg && msg.type === "SCAN_PICKED" && msg.result) {
    const r = msg.result;
    if (!r.ok) {
      scanResult.textContent = r.cancelled ? "Pick cancelled." : "Pick failed.";
      return;
    }
    _scanState.selector = r.selector || null;
    updateScanScopeIndicator();
    const jobs = Array.isArray(r.jobs) ? r.jobs : [];
    scanResult.textContent = jobs.length
      ? ""
      : "No postings found in that section.";
    markDuplicatesAndRender(jobs).catch(() => {});
  }
});

(async function init() {
  await loadTheme();
  await loadStatuses();
  await refreshStatus();
  const stored = await browser.storage.local.get([DRAFT_KEY, PICKED_KEY]);
  const haveDraft = !!stored[DRAFT_KEY];
  const havePicked = !!stored[PICKED_KEY];
  if (haveDraft || havePicked) {
    if (haveDraft) writeForm(stored[DRAFT_KEY]);
    else writeForm({ date: todayISO() });
    if (havePicked) {
      applyPicked(stored[PICKED_KEY]);
      await browser.storage.local.remove(PICKED_KEY);
    }
    showForm();
  }
})();
