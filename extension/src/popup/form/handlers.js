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
