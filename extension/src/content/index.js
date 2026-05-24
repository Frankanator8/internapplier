browser.runtime.onMessage.addListener((msg) => {
  if (msg && msg.type === "AUTOFILL") {
    const filled = autofillAll(msg.fields);
    return Promise.resolve({ filled });
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
    startPicker(msg.field);
    return Promise.resolve({ ok: true });
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
    if (fields) autofillAll(fields);
  } catch (_) { /* server not running — silent */ }
})();
