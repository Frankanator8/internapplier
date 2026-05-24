function extractJobList(rootEl) {
  const root = rootEl || document;
  const seen = new Set();
  const results = [];
  const push = (r) => {
    const key = (r.link || "") + "|" + normalize(r.company) + "|" + normalize(r.role);
    if (seen.has(key)) return;
    seen.add(key);
    results.push(r);
  };

  // Strategy A: real <table>
  const tables = root.querySelectorAll ? root.querySelectorAll("table") : [];
  for (const table of tables) {
    try {
      const rows = extractJobsFromTable(table);
      for (const r of rows) push(r);
    } catch (_) {}
  }
  if (root !== document && root.tagName === "TABLE") {
    try {
      const rows = extractJobsFromTable(root);
      for (const r of rows) push(r);
    } catch (_) {}
  }

  // Strategy B: ARIA grid
  try {
    const rows = extractJobsFromAriaGrid(root);
    for (const r of rows) push(r);
  } catch (_) {}

  // Strategy C: repeating-sibling lists
  try {
    const rows = extractJobsFromRepeatingList(root);
    for (const r of rows) push(r);
  } catch (_) {}

  return results;
}

function extractJobListWithRetry(rootEl, timeoutMs) {
  const initial = extractJobList(rootEl);
  if (initial.length > 0 || rootEl) {
    return Promise.resolve(initial);
  }
  // No results and scanning the whole document — wait briefly for SPA content
  return new Promise((resolve) => {
    let done = false;
    const finish = (jobs) => {
      if (done) return;
      done = true;
      try { observer.disconnect(); } catch (_) {}
      clearTimeout(timer);
      resolve(jobs);
    };
    const observer = new MutationObserver(() => {
      try {
        const got = extractJobList();
        if (got.length > 0) finish(got);
      } catch (_) {}
    });
    try {
      observer.observe(document.body, { childList: true, subtree: true });
    } catch (_) {
      finish(initial);
      return;
    }
    const timer = setTimeout(() => finish(extractJobList()), timeoutMs || 1500);
  });
}
