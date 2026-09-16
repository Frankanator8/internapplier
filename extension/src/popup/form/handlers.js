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
  showToast(`Picked ${picked.field}.`, { kind: "ok" });
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
  showToast("Reading page…", { persist: true });
  let meta = {};
  try {
    const reply = await browser.runtime.sendMessage({ type: "EXTRACT_PAGE_META" });
    if (reply && reply.needsRefresh) {
      showNeedsRefresh(reply.reason);
    } else if (reply && reply.ok) {
      meta = reply.meta || {};
      clearToast();
    } else {
      showToast((reply && reply.reason) || "Could not read the page.", { kind: "warn" });
    }
  } catch (_) {
    showToast("Could not read the page.", { kind: "warn" });
  }
  writeForm({
    company: meta.company || "",
    role: meta.role || "",
    date: todayISO(),
    link: meta.url || "",
    status: defaultStatus,
    notes: "",
    description: meta.description || "",
  });
  await saveDraft();
  showForm();
}

createBtn.addEventListener("click", () => {
  loadDraftOrExtract().catch((e) => {
    showToast(`Error: ${e.message}`, { kind: "error" });
  });
});

document.querySelectorAll(".pick-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const field = btn.getAttribute("data-pick-field") || "description";
    await saveDraft();
    await startPagePicker(
      field,
      `Click an element on the page to set ${field} (Esc to cancel).`
    );
  });
});

cancelBtn.addEventListener("click", async () => {
  await browser.storage.local.remove([DRAFT_KEY, PICKED_KEY]);
  clearToast();
  showMain();
});

saveBtn.addEventListener("click", async () => {
  const entry = readForm();
  if (!entry.company && !entry.role) {
    showToast("Company or Role required.", { kind: "warn" });
    return;
  }
  saveBtn.disabled = true;
  showToast("Saving…", { persist: true });
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
      showToast("Application saved.", { kind: "ok" });
      showMain();
      await populateLoadDropdown();
    } else {
      const detail = reply && (reply.error || (reply.body && JSON.stringify(reply.body)) || `HTTP ${reply.status}`);
      showToast(`Save failed: ${detail || "unknown error"}`, { kind: "error" });
    }
  } catch (e) {
    showToast(`Error: ${e.message}`, { kind: "error" });
  } finally {
    saveBtn.disabled = false;
  }
});

[fCompany, fRole, fDate, fLink, fStatus, fNotes, fDescription].forEach((el) => {
  el.addEventListener("input", saveDraft);
  el.addEventListener("change", saveDraft);
});
