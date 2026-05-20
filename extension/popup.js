const dot = document.getElementById("dot");
const statusText = document.getElementById("status-text");
const nameEl = document.getElementById("name");
const fillBtn = document.getElementById("fill-btn");
const createBtn = document.getElementById("create-btn");
const resultEl = document.getElementById("result");

const mainView = document.getElementById("main-view");
const formView = document.getElementById("form-view");
const fCompany = document.getElementById("f-company");
const fRole = document.getElementById("f-role");
const fDate = document.getElementById("f-date");
const fLink = document.getElementById("f-link");
const fStatus = document.getElementById("f-status");
const fNotes = document.getElementById("f-notes");
const fDescription = document.getElementById("f-description");
const pickBtn = document.getElementById("pick-btn");
const saveBtn = document.getElementById("save-btn");
const cancelBtn = document.getElementById("cancel-btn");
const formResult = document.getElementById("form-result");

const API_BASE = "http://127.0.0.1:8765";
const PICKED_KEY = "picked_description";
const DRAFT_KEY = "application_draft";

function todayISO() {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
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
  mainView.classList.remove("hidden");
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
  fStatus.value = data.status || "Applied";
  fNotes.value = data.notes || "";
  fDescription.value = data.description || "";
}

async function saveDraft() {
  try {
    await browser.storage.local.set({ [DRAFT_KEY]: readForm() });
  } catch (_) {}
}

async function loadDraftOrExtract() {
  const stored = await browser.storage.local.get([DRAFT_KEY, PICKED_KEY]);
  const draft = stored[DRAFT_KEY];
  const picked = stored[PICKED_KEY];
  if (draft) {
    writeForm(draft);
    if (picked) {
      fDescription.value = picked;
      await browser.storage.local.remove(PICKED_KEY);
      await saveDraft();
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
    status: "Applied",
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

pickBtn.addEventListener("click", async () => {
  await saveDraft();
  try {
    await browser.runtime.sendMessage({ type: "START_PICKER" });
    formResult.textContent = "Click an element on the page (Esc to cancel). Reopen the popup after picking.";
  } catch (e) {
    formResult.textContent = `Error: ${e.message}`;
  }
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
  try {
    const reply = await browser.runtime.sendMessage({
      type: "CREATE_APPLICATION",
      entry,
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

(async function init() {
  await refreshStatus();
  const stored = await browser.storage.local.get([DRAFT_KEY, PICKED_KEY]);
  if (stored[DRAFT_KEY] || stored[PICKED_KEY]) {
    if (stored[DRAFT_KEY]) writeForm(stored[DRAFT_KEY]);
    else writeForm({ date: todayISO() });
    if (stored[PICKED_KEY]) {
      fDescription.value = stored[PICKED_KEY];
      await browser.storage.local.remove(PICKED_KEY);
      await saveDraft();
    }
    showForm();
  }
})();
