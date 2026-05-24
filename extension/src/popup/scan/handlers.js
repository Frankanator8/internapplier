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
