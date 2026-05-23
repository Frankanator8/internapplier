const API_BASE = "http://127.0.0.1:8765";
const CACHE_KEY = "autofill_fields";
const PROFILE_CACHE_KEY = "profile_cache";
const STATUSES_CACHE_KEY = "statuses_cache";
const PICKED_KEY = "picked";

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

async function fetchProfile() {
  const res = await fetch(`${API_BASE}/profile`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${res.status}`);
  const data = await res.json();
  await browser.storage.local.set({ [PROFILE_CACHE_KEY]: data });
  return data;
}

async function getProfile({ forceRefresh = false } = {}) {
  if (!forceRefresh) {
    const stored = await browser.storage.local.get(PROFILE_CACHE_KEY);
    if (stored[PROFILE_CACHE_KEY]) return stored[PROFILE_CACHE_KEY];
  }
  return fetchProfile();
}

async function answerQuestion(question, applicationUuid) {
  try {
    const res = await fetch(`${API_BASE}/answer/question`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: question || "",
        application_uuid: applicationUuid || null,
      }),
    });
    let body = null;
    try { body = await res.json(); } catch (_) {}
    if (!res.ok) return { ok: false, status: res.status, error: (body && body.detail) || `HTTP ${res.status}` };
    return { ok: true, answer: (body && body.answer) || "" };
  } catch (e) {
    return { ok: false, status: 0, error: String(e && e.message || e) };
  }
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

async function extractPageMeta() {
  const tabId = await activeTabId();
  if (tabId == null) return { ok: false, reason: "no active tab" };
  try {
    const meta = await browser.tabs.sendMessage(tabId, { type: "EXTRACT_PAGE_META" });
    return { ok: true, meta };
  } catch (e) {
    return { ok: false, reason: String(e && e.message || e) };
  }
}

async function startPicker(field) {
  const tabId = await activeTabId();
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

async function extractJobList(selector) {
  const tabId = await activeTabId();
  if (tabId == null) return { ok: false, reason: "no active tab", jobs: [] };
  try {
    const reply = await browser.tabs.sendMessage(tabId, { type: "EXTRACT_JOB_LIST", selector: selector || null });
    if (reply && reply.ok) return { ok: true, jobs: reply.jobs || [] };
    return { ok: false, reason: (reply && reply.error) || "extraction failed", jobs: [] };
  } catch (e) {
    return { ok: false, reason: String(e && e.message || e), jobs: [] };
  }
}

async function bulkCreateApplications(entries) {
  try {
    const res = await fetch(`${API_BASE}/applications/bulk`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entries: entries || [] }),
    });
    let body = null;
    try { body = await res.json(); } catch (_) {}
    return { ok: res.ok, status: res.status, body };
  } catch (e) {
    return { ok: false, status: 0, error: String(e && e.message || e) };
  }
}

async function fetchResume(uuid) {
  if (!uuid) return { ok: false, error: "no uuid" };
  try {
    const res = await fetch(
      `${API_BASE}/applications/by-uuid/${encodeURIComponent(uuid)}/resume.pdf`,
      { cache: "no-store" }
    );
    if (!res.ok) return { ok: false, status: res.status };
    const cd = res.headers.get("Content-Disposition") || "";
    const m = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(cd);
    const filename = (m && decodeURIComponent(m[1])) || "Resume.pdf";
    const arrayBuffer = await res.arrayBuffer();
    return { ok: true, arrayBuffer, filename };
  } catch (e) {
    return { ok: false, status: 0, error: String(e && e.message || e) };
  }
}

async function attachLink(uuid, url) {
  if (!uuid) return { ok: false, error: "no uuid" };
  try {
    const res = await fetch(`${API_BASE}/applications/by-uuid/${encodeURIComponent(uuid)}/links`, {
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
  if (msg && msg.type === "GET_PROFILE") {
    return getProfile({ forceRefresh: !!msg.forceRefresh });
  }
  if (msg && msg.type === "ANSWER_QUESTION") {
    return answerQuestion(msg.question, msg.application_uuid);
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
  if (msg && msg.type === "AUTOFILL_WITH_APPLICATION") {
    return (async () => {
      const tabs = await browser.tabs.query({ active: true, currentWindow: true });
      if (!tabs[0]) return { ok: false, reason: "no active tab" };
      const fields = { ...(await getFields({ forceRefresh: true })) };
      try {
        const listed = await listApplications();
        if (listed.ok && Array.isArray(listed.body)) {
          const app = listed.body.find((a) => a.uuid === msg.uuid);
          if (app) {
            if (app.company) fields.company = app.company;
            if (app.role) fields.role = app.role;
            if (app.description) fields.description = app.description;
          }
        }
      } catch (_) {}
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
    return attachLink(msg.uuid, msg.url);
  }
  if (msg && msg.type === "FETCH_RESUME") {
    return fetchResume(msg.uuid);
  }
  if (msg && msg.type === "EXTRACT_JOB_LIST") {
    return extractJobList(msg.selector);
  }
  if (msg && msg.type === "SCAN_PICKER_RESULT") {
    // Forward to popup so it can render the scoped scan
    browser.runtime.sendMessage({ type: "SCAN_PICKED", result: msg.result }).catch(() => {});
    return Promise.resolve({ ok: true });
  }
  if (msg && msg.type === "BULK_CREATE_APPLICATIONS") {
    return bulkCreateApplications(msg.entries);
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

if (browser.browserAction && browser.browserAction.onClicked) {
  browser.browserAction.onClicked.addListener(() => {
    if (browser.sidebarAction && browser.sidebarAction.toggle) {
      browser.sidebarAction.toggle().catch(() => {});
    }
  });
}

// Warm the caches when the extension starts.
fetchFields().catch(() => {});
fetchStatuses().catch(() => {});
fetchProfile().catch(() => {});
