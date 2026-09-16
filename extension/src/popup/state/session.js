function emptySession() {
  return {
    view: "main",
    scan: { jobs: [], duplicates: [], selected: null, selector: null },
    selectedUuid: null,
    profileQuery: "",
  };
}

async function loadSession() {
  const stored = await browser.storage.local.get(SESSION_KEY);
  const s = stored[SESSION_KEY];
  const base = emptySession();
  if (!s || typeof s !== "object") return base;
  return {
    ...base,
    ...s,
    scan: { ...base.scan, ...(s.scan || {}) },
  };
}

async function patchSession(partial) {
  const current = await loadSession();
  const next = { ...current, ...partial };
  if (partial.scan) next.scan = { ...current.scan, ...partial.scan };
  await browser.storage.local.set({ [SESSION_KEY]: next });
  return next;
}
