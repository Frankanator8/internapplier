async function markDuplicatesAndRender(jobs) {
  let apps = [];
  try {
    const reply = await browser.runtime.sendMessage({ type: "LIST_APPLICATIONS" });
    if (reply && reply.ok && Array.isArray(reply.body)) apps = reply.body;
  } catch (_) {}
  const duplicates = jobs.map((j) => isDuplicate(j, apps));
  const newCount = duplicates.filter((d) => !d).length;
  _scanState.jobs = jobs;
  _scanState.duplicates = duplicates;
  scanSummary.textContent = `Found ${jobs.length} posting${jobs.length === 1 ? "" : "s"}, ${newCount} new.`;
  renderScanList();
}

async function runScan(selector) {
  showScan();
  scanResult.textContent = "";
  scanSummary.textContent = selector ? "Scanning section…" : "Scanning page…";
  scanList.innerHTML = "";
  _scanState.selector = selector || null;
  updateScanScopeIndicator();
  let jobs = [];
  try {
    const reply = await browser.runtime.sendMessage({
      type: "EXTRACT_JOB_LIST",
      selector: selector || null,
    });
    if (reply && reply.ok) jobs = reply.jobs || [];
    else scanResult.textContent = `Scan error: ${(reply && reply.reason) || "unknown"}`;
  } catch (e) {
    scanResult.textContent = `Error: ${e.message}`;
  }
  await markDuplicatesAndRender(jobs);
}
