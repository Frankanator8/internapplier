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
  if (msg && msg.type === "GENERATE_RESUME") {
    return startResumeGeneration(msg.uuid);
  }
  if (msg && msg.type === "GENERATE_RESUME_STATUS") {
    return getResumeGenerationStatus(msg.uuid);
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
