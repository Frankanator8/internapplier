function renderScanList() {
  scanList.innerHTML = "";
  if (!_scanState.jobs.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "No postings detected on this page. Try picking a section, or scan a careers listing.";
    scanList.appendChild(empty);
    return;
  }
  const selectedSet = Array.isArray(_scanState.selected)
    ? new Set(_scanState.selected)
    : null;
  _scanState.jobs.forEach((job, i) => {
    const dup = _scanState.duplicates[i];
    const row = document.createElement("label");
    row.className = "scan-row" + (dup ? " dup" : "");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = selectedSet ? selectedSet.has(i) : !dup;
    cb.dataset.idx = String(i);
    cb.addEventListener("change", persistScanSession);
    const main = document.createElement("div");
    main.className = "scan-main";
    const title = document.createElement("div");
    title.className = "scan-title";
    const company = job.company || "(no company)";
    const role = job.role || "(no role)";
    title.textContent = `${company} — ${role}`;
    title.title = title.textContent;
    main.appendChild(title);
    let subText = "";
    try { subText = job.link ? new URL(job.link).host : ""; } catch (_) { subText = job.link || ""; }
    if (job.location) subText = subText ? `${subText} · ${job.location}` : job.location;
    if (subText) {
      const sub = document.createElement("div");
      sub.className = "scan-sub";
      sub.textContent = subText;
      sub.title = subText;
      main.appendChild(sub);
    }
    row.appendChild(cb);
    row.appendChild(main);
    if (dup) {
      const badge = document.createElement("span");
      badge.className = "badge";
      badge.textContent = "already added";
      row.appendChild(badge);
    }
    scanList.appendChild(row);
  });
}
