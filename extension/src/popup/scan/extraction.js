async function markDuplicatesAndRender(jobs, { restoreSelected = false } = {}) {
  let apps = [];
  try {
    const reply = await browser.runtime.sendMessage({ type: "LIST_APPLICATIONS" });
    if (reply && reply.ok && Array.isArray(reply.body)) apps = reply.body;
  } catch (_) {}
  const duplicates = jobs.map((j) => isDuplicate(j, apps));
  const newCount = duplicates.filter((d) => !d).length;
  _scanState.jobs = jobs;
  _scanState.duplicates = duplicates;
  if (!restoreSelected) _scanState.selected = null;
  scanSummary.textContent = `Found ${jobs.length} posting${jobs.length === 1 ? "" : "s"}, ${newCount} new.`;
  renderScanList();
  persistScanSession();
}

async function runScan(selector) {
  showScan();
  clearToast();
  scanSummary.textContent = selector ? "Scanning section…" : "Scanning page…";
  scanList.innerHTML = "";
  _scanState.selector = selector || null;
  _scanState.selected = null;
  updateScanScopeIndicator();
  let jobs = [];
  try {
    const reply = await browser.runtime.sendMessage({
      type: "EXTRACT_JOB_LIST",
      selector: selector || null,
    });
    if (reply && reply.needsRefresh) {
      showNeedsRefresh(reply.reason);
    } else if (reply && reply.ok) {
      jobs = reply.jobs || [];
    } else {
      showToast(`Scan error: ${(reply && reply.reason) || "unknown"}`, { kind: "error" });
    }
  } catch (e) {
    showToast(`Error: ${e.message}`, { kind: "error" });
  }
  await markDuplicatesAndRender(jobs);
}

function restoreScanView(scan) {
  _scanState.jobs = Array.isArray(scan.jobs) ? scan.jobs : [];
  _scanState.duplicates = Array.isArray(scan.duplicates) ? scan.duplicates : [];
  _scanState.selector = scan.selector || null;
  _scanState.selected = Array.isArray(scan.selected) ? scan.selected : null;
  updateScanScopeIndicator();
  const newCount = _scanState.duplicates.filter((d) => !d).length;
  scanSummary.textContent = _scanState.jobs.length
    ? `Found ${_scanState.jobs.length} posting${_scanState.jobs.length === 1 ? "" : "s"}, ${newCount} new.`
    : "No postings stored.";
  renderScanList();
}
