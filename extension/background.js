const API_BASE = "http://127.0.0.1:8765";
const CACHE_KEY = "autofill_fields";
const STATUSES_CACHE_KEY = "statuses_cache";
const PICKED_KEY = "picked";
const PICKER_TAB_KEY = "picker_tab_id";

async function fetchStatuses() {
  const res = await fetch(`${API_BASE}/statuses`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${res.status}`);
  const data = await res.json();
  await browser.storage.local.set({ [STATUSES_CACHE_KEY]: data });
  return data;
}

async function getStatuses({ forceRefresh = false } = {}) {
  if (!forceRefresh) {
    const stored = await browser.storage.local.get(STATUSES_CACHE_KEY);
    if (stored[STATUSES_CACHE_KEY]) return stored[STATUSES_CACHE_KEY];
  }
  return fetchStatuses();
}

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

async function activeTabId() {
  const tabs = await browser.tabs.query({ active: true, currentWindow: true });
  return tabs[0] ? tabs[0].id : null;
}

async function pageTabId() {
  try {
    const stored = await browser.storage.local.get(PICKER_TAB_KEY);
    if (stored[PICKER_TAB_KEY] != null) return stored[PICKER_TAB_KEY];
  } catch (_) {}
  return activeTabId();
}

async function extractPageMeta() {
  const tabId = await pageTabId();
  if (tabId == null) return { ok: false, reason: "no active tab" };
  try {
    const meta = await browser.tabs.sendMessage(tabId, { type: "EXTRACT_PAGE_META" });
    return { ok: true, meta };
  } catch (e) {
    return { ok: false, reason: String(e && e.message || e) };
  }
}

async function startPicker(field) {
  const tabId = await pageTabId();
  if (tabId == null) return { ok: false, reason: "no active tab" };
  try {
    await browser.storage.local.remove(PICKED_KEY);
  } catch (_) {}
  try {
    await browser.tabs.sendMessage(tabId, { type: "START_PICKER", field: field || "description" });
    return { ok: true };
  } catch (e) {
    return { ok: false, reason: String(e && e.message || e) };
  }
}

async function openDetachedForm() {
  try {
    const tabId = await activeTabId();
    if (tabId != null) {
      await browser.storage.local.set({ [PICKER_TAB_KEY]: tabId });
    }
  } catch (_) {}
  try {
    await browser.windows.create({
      url: browser.runtime.getURL("popup.html?detached=1"),
      type: "popup",
      width: 380,
      height: 760,
    });
    return { ok: true };
  } catch (e) {
    return { ok: false, reason: String(e && e.message || e) };
  }
}

async function createApplication(entry) {
  try {
    const res = await fetch(`${API_BASE}/applications`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(entry || {}),
    });
    let body = null;
    try { body = await res.json(); } catch (_) {}
    return { ok: res.ok, status: res.status, body };
  } catch (e) {
    return { ok: false, status: 0, error: String(e && e.message || e) };
  }
}

async function listApplications() {
  try {
    const res = await fetch(`${API_BASE}/applications`, { cache: "no-store" });
    let body = null;
    try { body = await res.json(); } catch (_) {}
    return { ok: res.ok, status: res.status, body };
  } catch (e) {
    return { ok: false, status: 0, error: String(e && e.message || e) };
  }
}

async function attachLink(index, url) {
  try {
    const res = await fetch(`${API_BASE}/applications/${index}/links`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url || "" }),
    });
    let body = null;
    try { body = await res.json(); } catch (_) {}
    return { ok: res.ok, status: res.status, body };
  } catch (e) {
    return { ok: false, status: 0, error: String(e && e.message || e) };
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
  if (msg && msg.type === "EXTRACT_PAGE_META") {
    return extractPageMeta();
  }
  if (msg && msg.type === "START_PICKER") {
    return startPicker(msg.field);
  }
  if (msg && msg.type === "OPEN_DETACHED_FORM") {
    return openDetachedForm();
  }
  if (msg && msg.type === "GET_STATUSES") {
    return getStatuses({ forceRefresh: !!msg.forceRefresh });
  }
  if (msg && msg.type === "CREATE_APPLICATION") {
    return createApplication(msg.entry);
  }
  if (msg && msg.type === "LIST_APPLICATIONS") {
    return listApplications();
  }
  if (msg && msg.type === "ATTACH_LINK") {
    return attachLink(msg.index, msg.url);
  }
  if (msg && msg.type === "PICKER_RESULT") {
    if (msg.result && msg.result.ok && msg.result.field) {
      const payload = { field: msg.result.field, value: msg.result.value || "" };
      browser.storage.local.set({ [PICKED_KEY]: payload }).catch(() => {});
      browser.runtime.sendMessage({ type: "PICKED", picked: payload }).catch(() => {});
    }
    return Promise.resolve({ ok: true });
  }
});

// Warm the caches when the extension starts.
fetchFields().catch(() => {});
fetchStatuses().catch(() => {});
