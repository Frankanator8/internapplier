browser.runtime.onMessage.addListener((msg, _sender) => {
  if (msg && msg.type === "GET_FIELDS") {
    return getFields({ forceRefresh: !!msg.forceRefresh });
  }
  if (msg && msg.type === "GET_PROFILE") {
    return getProfile({ forceRefresh: !!msg.forceRefresh });
  }
  if (msg && msg.type === "ANSWER_QUESTION") {
    return startAnswerJob(msg.question, msg.application_uuid);
  }
  if (msg && msg.type === "RETRY_ANSWER") {
    return retryAnswer(msg.id);
  }
  if (msg && msg.type === "DISMISS_ANSWER") {
    return dismissAnswer(msg.id);
  }
  if (msg && msg.type === "HEALTH") {
    return checkHealth();
  }
  if (msg && msg.type === "AUTOFILL_ACTIVE_TAB") {
    return (async () => {
      let loaded;
      try {
        loaded = await loadFieldsForAutofill();
      } catch (e) {
        return { ok: false, error: String(e && e.message || e) };
      }
      const reply = await sendToActiveTab({ type: "AUTOFILL", fields: loaded.fields });
      if (reply && reply.needsRefresh) {
        return { ok: false, needsRefresh: true, error: reply.reason, stale: loaded.stale, fetchedAt: loaded.fetchedAt };
      }
      if (reply && reply.ok === false) {
        return { ok: false, error: reply.reason || "autofill failed", stale: loaded.stale, fetchedAt: loaded.fetchedAt };
      }
      return {
        ok: true,
        report: {
          filled: (reply && reply.filled) || [],
          skipped: (reply && reply.skipped) || [],
        },
        stale: loaded.stale,
        fetchedAt: loaded.fetchedAt,
      };
    })();
  }
  if (msg && msg.type === "AUTOFILL_WITH_APPLICATION") {
    return (async () => {
      let loaded;
      try {
        loaded = await loadFieldsForAutofill();
      } catch (e) {
        return { ok: false, error: String(e && e.message || e) };
      }
      const fields = { ...loaded.fields };
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
      const reply = await sendToActiveTab({ type: "AUTOFILL", fields });
      if (reply && reply.needsRefresh) {
        return { ok: false, needsRefresh: true, error: reply.reason, stale: loaded.stale, fetchedAt: loaded.fetchedAt };
      }
      if (reply && reply.ok === false) {
        return { ok: false, error: reply.reason || "autofill failed", stale: loaded.stale, fetchedAt: loaded.fetchedAt };
      }
      return {
        ok: true,
        report: {
          filled: (reply && reply.filled) || [],
          skipped: (reply && reply.skipped) || [],
        },
        stale: loaded.stale,
        fetchedAt: loaded.fetchedAt,
      };
    })();
  }
  if (msg && msg.type === "EXTRACT_PAGE_META") {
    return extractPageMeta();
  }
  if (msg && msg.type === "START_PICKER") {
    return startPicker(msg.field);
  }
  if (msg && msg.type === "RELOAD_ACTIVE_TAB") {
    return reloadActiveTab();
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
    } else {
      browser.runtime.sendMessage({
        type: "PICKED",
        picked: null,
        cancelled: !!(msg.result && msg.result.cancelled),
        result: msg.result || { ok: false },
      }).catch(() => {});
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

fetchFields().catch(() => {});
fetchStatuses().catch(() => {});
fetchProfile().catch(() => {});
