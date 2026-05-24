function extractFromRepeatingRows(rows) {
  const out = [];
  for (const row of rows) {
    if (!row || row.nodeType !== 1) continue;
    const text = deepText(row);
    if (!text) continue;
    const anchors = Array.from(row.querySelectorAll("a[href]")).filter((a) => {
      const href = a.getAttribute("href") || "";
      return href && !/^(mailto:|javascript:|#)/i.test(href);
    });
    if (!anchors.length) continue;

    // Role: longest anchor text, or first heading
    let role = "";
    const heading = row.querySelector("h1, h2, h3, h4, h5, [role='heading']");
    if (heading) role = deepText(heading, 200);
    if (!role) {
      let best = "";
      for (const a of anchors) {
        const t = deepText(a, 200);
        if (t.length > best.length) best = t;
      }
      role = best;
    }

    // Company: try data attrs / aria-labels, else fall back to other anchor text
    let company = "";
    const compEl = row.querySelector(
      '[data-company], [data-company-name], [class*="company" i], [aria-label*="company" i]'
    );
    if (compEl) company = deepText(compEl, 120);
    if (!company) {
      for (const a of anchors) {
        const t = deepText(a, 120);
        if (t && t !== role) { company = t; break; }
      }
    }

    // Location
    const location = pickLocation(text);

    // Link: first non-trivial anchor
    const link = anchors[0].href;

    if (!role && !company) continue;
    out.push({ company, role, link, location });
  }
  return out;
}

function extractJobsFromRepeatingList(root) {
  const results = [];
  // Candidate containers: root + descendants with ≥ 4 element children
  const candidates = [root];
  const all = root.querySelectorAll ? root.querySelectorAll("*") : [];
  for (const el of all) {
    if (el.children && el.children.length >= 4) candidates.push(el);
  }
  for (const container of candidates) {
    const kids = Array.from(container.children || []);
    if (kids.length < 4) continue;
    // Group by signature
    const groups = new Map();
    for (const k of kids) {
      const sig = signatureFor(k);
      if (!sig) continue;
      if (!groups.has(sig)) groups.set(sig, []);
      groups.get(sig).push(k);
    }
    for (const [, group] of groups) {
      if (group.length < 4) continue;
      // Must contain at least one anchor in most rows
      const withLinks = group.filter((r) => r.querySelector && r.querySelector("a[href]"));
      if (withLinks.length < Math.max(2, Math.floor(group.length * 0.5))) continue;
      const rows = extractFromRepeatingRows(group);
      for (const r of rows) results.push(r);
    }
  }
  return results;
}
