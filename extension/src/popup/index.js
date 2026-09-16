browser.runtime.onMessage.addListener((msg) => {
  if (msg && msg.type === "PICKED") {
    if (msg.cancelled || (msg.result && !msg.result.ok)) {
      showToast(msg.cancelled ? "Pick cancelled." : "Pick failed.", { kind: "warn" });
      return;
    }
    if (msg.picked && msg.picked.field === "question") {
      browser.storage.local.remove(PICKED_KEY).catch(() => {});
      askQuestion(msg.picked.value);
      return;
    }
    if (msg.picked) {
      applyPicked(msg.picked);
      browser.storage.local.remove(PICKED_KEY).catch(() => {});
    }
  }
  if (msg && msg.type === "SCAN_PICKED" && msg.result) {
    const r = msg.result;
    if (!r.ok) {
      showToast(r.cancelled ? "Pick cancelled." : "Pick failed.", { kind: "warn" });
      return;
    }
    _scanState.selector = r.selector || null;
    updateScanScopeIndicator();
    const jobs = Array.isArray(r.jobs) ? r.jobs : [];
    if (!jobs.length) {
      showToast("No postings found in that section.", { kind: "warn" });
    } else {
      clearToast();
    }
    markDuplicatesAndRender(jobs).catch(() => {});
  }
  if (msg && msg.type === "ANSWER_UPDATED" && msg.entry) {
    upsertAnswerCard(msg.entry);
    if (msg.entry.status === "done") {
      (async () => {
        try {
          await navigator.clipboard.writeText(msg.entry.answer || "");
          showToast("Answer ready — copied to clipboard.", { kind: "ok" });
        } catch (_) {
          showToast("Answer ready — could not copy. Use the Copy button.", { kind: "warn" });
        }
      })();
    } else if (msg.entry.status === "error") {
      showToast("AI answer failed.", { kind: "error" });
    }
  }
  if (msg && msg.type === "ANSWER_DISMISSED" && msg.id) {
    const card = document.getElementById(msg.id);
    if (card) card.remove();
    ensureAnswersVisible();
  }
});

(async function init() {
  await loadTheme();
  await loadStatuses();
  await restoreAnswerCards();

  let session = emptySession();
  try {
    session = await loadSession();
  } catch (_) {}

  if (session.profileQuery && profileSearch) {
    profileSearch.value = session.profileQuery;
  }

  await refreshStatus();

  const stored = await browser.storage.local.get([DRAFT_KEY, PICKED_KEY]);
  const picked = stored[PICKED_KEY];

  if (picked && picked.field === "question") {
    await browser.storage.local.remove(PICKED_KEY);
    showMain();
    askQuestion(picked.value);
    return;
  }

  if (stored[DRAFT_KEY] || picked) {
    if (stored[DRAFT_KEY]) writeForm(stored[DRAFT_KEY]);
    else writeForm({ date: todayISO() });
    if (picked) {
      applyPicked(picked);
      await browser.storage.local.remove(PICKED_KEY);
    }
    showForm();
    return;
  }

  if (session.view === "scan") {
    restoreScanView(session.scan || emptySession().scan);
    showScan();
    return;
  }

  showMain();
})();
