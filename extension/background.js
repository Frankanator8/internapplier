const API_BASE = "http://127.0.0.1:8765";
const CACHE_KEY = "autofill_fields";

async function fetchFields() {
  const res = await fetch(`${API_BASE}/autofill/fields`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${res.status}`);
  const fields = await res.json();
  await browser.storage.local.set({ [CACHE_KEY]: fields });
  return fields;
}

async function getFields({ forceRefresh = false } = {}) {
  if (!forceRefresh) {
    const stored = await browser.storage.local.get(CACHE_KEY);
    if (stored[CACHE_KEY]) return stored[CACHE_KEY];
  }
  return fetchFields();
}

async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
    return res.ok;
  } catch (_) {
    return false;
  }
}

browser.runtime.onMessage.addListener((msg, _sender) => {
  if (msg && msg.type === "GET_FIELDS") {
    return getFields({ forceRefresh: !!msg.forceRefresh });
  }
  if (msg && msg.type === "HEALTH") {
    return checkHealth();
  }
  if (msg && msg.type === "AUTOFILL_ACTIVE_TAB") {
    return (async () => {
      const tabs = await browser.tabs.query({ active: true, currentWindow: true });
      if (!tabs[0]) return { ok: false, reason: "no active tab" };
      const fields = await getFields({ forceRefresh: true });
      await browser.tabs.sendMessage(tabs[0].id, { type: "AUTOFILL", fields });
      return { ok: true };
    })();
  }
});

// Warm the cache when the extension starts.
fetchFields().catch(() => {});
