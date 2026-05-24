function normText(s) {
  return (s || "").toString().toLowerCase().replace(/\s+/g, " ").trim();
}

let _scanState = { jobs: [], duplicates: [], selector: null };

function updateScanScopeIndicator() {
  if (_scanState.selector) {
    scanScopeSelector.textContent = _scanState.selector;
    scanScope.classList.remove("hidden");
  } else {
    scanScope.classList.add("hidden");
  }
}

function isDuplicate(job, apps) {
  const link = (job.link || "").trim();
  const company = normText(job.company);
  const role = normText(job.role);
  for (const a of apps) {
    const links = Array.isArray(a.links) ? a.links : [];
    if (link && links.includes(link)) return true;
    if (company && role && normText(a.company) === company && normText(a.role) === role) return true;
  }
  return false;
}
