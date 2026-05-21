const dot = document.getElementById("dot");
const statusText = document.getElementById("status-text");
const nameEl = document.getElementById("name");
const fillBtn = document.getElementById("fill-btn");
const createBtn = document.getElementById("create-btn");
const addLinkBtn = document.getElementById("add-link-btn");
const resultEl = document.getElementById("result");

const attachView = document.getElementById("attach-view");
const attachUrlEl = document.getElementById("attach-url");
const attachTarget = document.getElementById("attach-target");
const attachSaveBtn = document.getElementById("attach-save-btn");
const attachCancelBtn = document.getElementById("attach-cancel-btn");
const attachResult = document.getElementById("attach-result");

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

const FIELD_TO_INPUT = {
  company: fCompany,
  role: fRole,
  date: fDate,
  link: fLink,
  notes: fNotes,
  description: fDescription,
};

let defaultStatus = "Applied";

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
    fillBtn.disabled = false;
    createBtn.disabled = false;
    if (addLinkBtn) addLinkBtn.disabled = false;
    try {
      const res = await fetch(`${API_BASE}/profile/general_info`);
      const info = await res.json();
      const name = [info.first_name, info.last_name].filter(Boolean).join(" ");
      nameEl.textContent = name ? `Profile: ${name}` : "Profile loaded (no name)";
    } catch (_) {
      nameEl.textContent = "";
    }
  } else {
    dot.classList.add("err");
    statusText.textContent = "Server unreachable";
    fillBtn.disabled = true;
    createBtn.disabled = true;
    if (addLinkBtn) addLinkBtn.disabled = true;
    nameEl.textContent = "";
  }
}

fillBtn.addEventListener("click", async () => {
  resultEl.textContent = "Filling…";
  fillBtn.disabled = true;
  try {
    const reply = await browser.runtime.sendMessage({ type: "AUTOFILL_ACTIVE_TAB" });
    resultEl.textContent = reply && reply.ok ? "Done." : "Could not autofill.";
  } catch (e) {
    resultEl.textContent = `Error: ${e.message}`;
  } finally {
    fillBtn.disabled = false;
  }
});

function showForm() {
  mainView.classList.add("hidden");
  formView.classList.remove("hidden");
}

function showMain() {
  formView.classList.add("hidden");
  if (attachView) attachView.classList.add("hidden");
  mainView.classList.remove("hidden");
}

function showAttach() {
  mainView.classList.add("hidden");
  formView.classList.add("hidden");
  attachView.classList.remove("hidden");
}

function pickBestMatch(apps, meta) {
  if (!Array.isArray(apps) || !apps.length) return -1;
  const company = (meta.company || "").toLowerCase().trim();
  const role = (meta.role || "").toLowerCase().trim();
  if (company) {
    for (const a of apps) {
      if ((a.company || "").toLowerCase().trim() === company) return a.index;
    }
  }
  if (role) {
    for (const a of apps) {
      if ((a.role || "").toLowerCase().trim() === role) return a.index;
    }
  }
  return apps[0].index;
}

async function openAttachView() {
  attachResult.textContent = "Loading…";
  attachTarget.innerHTML = "";
  attachUrlEl.textContent = "";
  let meta = {};
  try {
    const reply = await browser.runtime.sendMessage({ type: "EXTRACT_PAGE_META" });
    if (reply && reply.ok) meta = reply.meta || {};
  } catch (_) {}
  const url = meta.url || "";
  attachUrlEl.textContent = url || "(unknown URL)";
  attachView.dataset.url = url;

  let apps = [];
  let listErr = "";
  try {
    const reply = await browser.runtime.sendMessage({ type: "LIST_APPLICATIONS" });
    if (reply && reply.ok && Array.isArray(reply.body)) {
      apps = reply.body;
    } else if (!reply) {
      listErr = "Background script did not respond — reload the extension.";
    } else {
      listErr = reply.error || `HTTP ${reply.status}` || "unexpected response";
    }
  } catch (e) {
    listErr = String(e && e.message || e);
  }

  if (!apps.length) {
    attachResult.textContent = listErr
      ? `Could not load applications: ${listErr}`
      : "No existing applications. Create one first.";
    showAttach();
    return;
  }

  for (const a of apps) {
    const opt = document.createElement("option");
    opt.value = String(a.index);
    const company = a.company || "(no company)";
    const role = a.role || "(no role)";
    const count = (a.links || []).length;
    opt.textContent = `${company} — ${role}${count ? ` (${count} link${count === 1 ? "" : "s"})` : ""}`;
    attachTarget.appendChild(opt);
  }
  const best = pickBestMatch(apps, meta);
  if (best >= 0) attachTarget.value = String(best);
  attachResult.textContent = "";
  showAttach();
}

if (addLinkBtn) {
  addLinkBtn.addEventListener("click", () => {
    openAttachView().catch((e) => {
      resultEl.textContent = `Error: ${e.message}`;
    });
  });
}

if (attachCancelBtn) {
  attachCancelBtn.addEventListener("click", () => {
    attachResult.textContent = "";
    showMain();
  });
}

if (attachSaveBtn) {
  attachSaveBtn.addEventListener("click", async () => {
    const url = (attachView.dataset.url || "").trim();
    const idxStr = attachTarget.value;
    if (!url) {
      attachResult.textContent = "No page URL detected.";
      return;
    }
    if (idxStr === "" || idxStr == null) {
      attachResult.textContent = "Pick an application.";
      return;
    }
    const index = parseInt(idxStr, 10);
    attachSaveBtn.disabled = true;
    attachResult.textContent = "Saving…";
    try {
      const reply = await browser.runtime.sendMessage({
        type: "ATTACH_LINK",
        index,
        url,
      });
      if (reply && reply.ok) {
        resultEl.textContent = "Link added.";
        showMain();
      } else {
        const detail = reply && (reply.error || (reply.body && JSON.stringify(reply.body)) || `HTTP ${reply.status}`);
        attachResult.textContent = `Failed: ${detail || "unknown error"}`;
      }
    } catch (e) {
      attachResult.textContent = `Error: ${e.message}`;
    } finally {
      attachSaveBtn.disabled = false;
    }
  });
}

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

browser.runtime.onMessage.addListener((msg) => {
  if (msg && msg.type === "PICKED" && msg.picked) {
    applyPicked(msg.picked);
    browser.storage.local.remove(PICKED_KEY).catch(() => {});
  }
});

(async function init() {
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
