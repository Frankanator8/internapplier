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
