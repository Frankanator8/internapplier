scanBtn.addEventListener("click", () => {
  runScan().catch((e) => { showToast(`Error: ${e.message}`, { kind: "error" }); });
});

scanBack.addEventListener("click", () => {
  showMain();
});

scanPick.addEventListener("click", async () => {
  await startPagePicker(
    "scan_container",
    "Click an element on the page to scope the scan (Esc to cancel)…"
  );
});

scanScopeClear.addEventListener("click", () => {
  runScan(null).catch((e) => { showToast(`Error: ${e.message}`, { kind: "error" }); });
});

scanSelectNew.addEventListener("click", () => {
  scanList.querySelectorAll("input[type=checkbox]").forEach((cb) => {
    const idx = parseInt(cb.dataset.idx, 10);
    cb.checked = !_scanState.duplicates[idx];
  });
  persistScanSession();
});

scanDeselect.addEventListener("click", () => {
  scanList.querySelectorAll("input[type=checkbox]").forEach((cb) => { cb.checked = false; });
  persistScanSession();
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
    showToast("Nothing selected.", { kind: "warn" });
    return;
  }
  scanAdd.disabled = true;
  showToast(`Adding ${selected.length}…`, { persist: true });
  try {
    const reply = await browser.runtime.sendMessage({
      type: "BULK_CREATE_APPLICATIONS",
      entries: selected,
    });
    if (reply && reply.ok) {
      const added = (reply.body && reply.body.added) || selected.length;
      showToast(`Added ${added} application${added === 1 ? "" : "s"}.`, { kind: "ok" });
      await populateLoadDropdown();
      const apps = (await browser.runtime.sendMessage({ type: "LIST_APPLICATIONS" })) || {};
      const list = (apps.ok && Array.isArray(apps.body)) ? apps.body : [];
      _scanState.duplicates = _scanState.jobs.map((j) => isDuplicate(j, list));
      _scanState.selected = null;
      renderScanList();
      persistScanSession();
    } else {
      const detail = reply && (reply.error || (reply.body && JSON.stringify(reply.body)) || `HTTP ${reply.status}`);
      showToast(`Add failed: ${detail || "unknown error"}`, { kind: "error" });
    }
  } catch (e) {
    showToast(`Error: ${e.message}`, { kind: "error" });
  } finally {
    scanAdd.disabled = false;
  }
});
