async function activeTabId() {
  const tabs = await browser.tabs.query({ active: true, currentWindow: true });
  return tabs[0] ? tabs[0].id : null;
}

function tabMessageError(e) {
  const reason = String(e && e.message || e);
  const needsRefresh = /Receiving end does not exist|Could not establish connection/i.test(reason);
  return {
    ok: false,
    reason: needsRefresh
      ? "Reload the page so InternApplier can attach."
      : reason,
    needsRefresh,
  };
}

async function sendToActiveTab(message) {
  const tabId = await activeTabId();
  if (tabId == null) return { ok: false, reason: "no active tab" };
  try {
    return await browser.tabs.sendMessage(tabId, message);
  } catch (e) {
    return tabMessageError(e);
  }
}

async function extractPageMeta() {
  const tabId = await activeTabId();
  if (tabId == null) return { ok: false, reason: "no active tab" };
  try {
    const meta = await browser.tabs.sendMessage(tabId, { type: "EXTRACT_PAGE_META" });
    return { ok: true, meta };
  } catch (e) {
    return tabMessageError(e);
  }
}

async function startPicker(field) {
  const tabId = await activeTabId();
  if (tabId == null) return { ok: false, reason: "no active tab" };
  try {
    await browser.storage.local.remove(PICKED_KEY);
  } catch (_) {}
  try {
    const reply = await browser.tabs.sendMessage(
      tabId,
      { type: "START_PICKER", field: field || "description" }
    );
    if (reply && reply.ok === false) {
      return { ok: false, reason: reply.reason || "picker failed", needsRefresh: !!reply.needsRefresh };
    }
    return { ok: true };
  } catch (e) {
    return tabMessageError(e);
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
    return { ...tabMessageError(e), jobs: [] };
  }
}

async function reloadActiveTab() {
  const tabId = await activeTabId();
  if (tabId == null) return { ok: false, reason: "no active tab" };
  try {
    await browser.tabs.reload(tabId);
    return { ok: true };
  } catch (e) {
    return { ok: false, reason: String(e && e.message || e) };
  }
}
