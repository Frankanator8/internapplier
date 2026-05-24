async function fetchStatuses() {
  const res = await fetch(`${API_BASE}/statuses`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${res.status}`);
  const data = await res.json();
  await browser.storage.local.set({ [STATUSES_CACHE_KEY]: data });
  return data;
}

async function fetchFields() {
  const res = await fetch(`${API_BASE}/autofill/fields`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${res.status}`);
  const fields = await res.json();
  await browser.storage.local.set({ [CACHE_KEY]: fields });
  return fields;
}

async function fetchProfile() {
  const res = await fetch(`${API_BASE}/profile`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${res.status}`);
  const data = await res.json();
  await browser.storage.local.set({ [PROFILE_CACHE_KEY]: data });
  return data;
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

async function startResumeGeneration(uuid) {
  if (!uuid) return { ok: false, error: "no uuid" };
  try {
    const res = await fetch(
      `${API_BASE}/applications/by-uuid/${encodeURIComponent(uuid)}/resume/generate`,
      { method: "POST" }
    );
    let body = null;
    try { body = await res.json(); } catch (_) {}
    return { ok: res.ok, status: res.status, body };
  } catch (e) {
    return { ok: false, status: 0, error: String(e && e.message || e) };
  }
}

async function getResumeGenerationStatus(uuid) {
  if (!uuid) return { ok: false, error: "no uuid" };
  try {
    const res = await fetch(
      `${API_BASE}/applications/by-uuid/${encodeURIComponent(uuid)}/resume/generate/status`,
      { cache: "no-store" }
    );
    let body = null;
    try { body = await res.json(); } catch (_) {}
    return { ok: res.ok, status: res.status, body };
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
