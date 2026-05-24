function applyProfileFilter() {
  const query = (profileSearch.value || "").toLowerCase().trim();
  const rows = profileTree.querySelectorAll(".chip-row");
  rows.forEach((row) => {
    if (!query) {
      row.style.display = "";
      return;
    }
    const fieldName = row.querySelector(".field-name");
    const chip = row.querySelector(".chip");
    const hay = [
      fieldName ? fieldName.textContent : "",
      chip ? chip.textContent : "",
      chip ? chip.title : "",
    ].join(" ").toLowerCase();
    row.style.display = hay.includes(query) ? "" : "none";
  });

  const allDetails = Array.from(profileTree.querySelectorAll("details.tree"));
  const summaryMatches = new Set();
  if (query) {
    for (const d of allDetails) {
      const s = d.querySelector(":scope > summary");
      if (s && s.textContent.toLowerCase().includes(query)) {
        summaryMatches.add(d);
        d.querySelectorAll(".chip-row").forEach((r) => { r.style.display = ""; });
      }
    }
  }

  for (let i = allDetails.length - 1; i >= 0; i--) {
    const d = allDetails[i];
    if (!query) {
      d.style.display = "";
      d.open = d.dataset.defaultOpen === "1";
      continue;
    }
    const hasVisibleRow = Array.from(d.querySelectorAll(".chip-row"))
      .some((r) => r.style.display !== "none");
    const hasVisibleChild = Array.from(d.querySelectorAll(":scope > .tree-body > details.tree"))
      .some((c) => c.style.display !== "none");
    const visible = summaryMatches.has(d) || hasVisibleRow || hasVisibleChild;
    d.style.display = visible ? "" : "none";
    d.open = visible;
  }

  const visibleRows = Array.from(rows).some((r) => r.style.display !== "none");
  const visibleDetails = allDetails.some((d) => d.style.display !== "none");
  profileEmpty.classList.toggle("hidden", !query || visibleRows || visibleDetails);
}

profileSearch.addEventListener("input", applyProfileFilter);
