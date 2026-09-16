browser.runtime.onMessage.addListener((msg) => {
  if (msg && msg.type === "AUTOFILL") {
    const report = autofillAll(msg.fields);
    return Promise.resolve(report);
  }
  if (msg && msg.type === "EXTRACT_PAGE_META") {
    try {
      return Promise.resolve(extractPageMeta());
    } catch (e) {
      return Promise.resolve({
        url: location.href, title: document.title,
        role: "", company: "", description: "",
        error: String(e && e.message || e),
      });
    }
  }
  if (msg && msg.type === "START_PICKER") {
    const result = startPicker(msg.field);
    return Promise.resolve(result || { ok: true });
  }
  if (msg && msg.type === "EXTRACT_JOB_LIST") {
    let root = null;
    if (msg.selector) {
      try { root = document.querySelector(msg.selector); } catch (_) {}
    }
    return extractJobListWithRetry(root, 1500).then(
      (jobs) => ({ ok: true, jobs }),
      (e) => ({ ok: false, error: String(e && e.message || e), jobs: [] })
    );
  }
});

(async function autoRunOnLoad() {
  try {
    const fields = await browser.runtime.sendMessage({ type: "GET_FIELDS" });
    if (!fields || typeof fields !== "object") return;
    const report = autofillAll(fields);
    const n = report && Array.isArray(report.filled) ? report.filled.length : 0;
    if (n > 0) {
      showPageToast(`InternApplier filled ${n} field${n === 1 ? "" : "s"}.`);
    }
  } catch (_) { /* server not running — silent */ }
})();
