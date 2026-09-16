async function getStatuses({ forceRefresh = false } = {}) {
  if (!forceRefresh) {
    const stored = await browser.storage.local.get(STATUSES_CACHE_KEY);
    if (stored[STATUSES_CACHE_KEY]) return stored[STATUSES_CACHE_KEY];
  }
  return fetchStatuses();
}

async function peekCachedFields() {
  const stored = await browser.storage.local.get(CACHE_KEY);
  const cached = stored[CACHE_KEY];
  if (!cached || typeof cached !== "object") return null;
  if (cached.fields && typeof cached.fields === "object" && !Array.isArray(cached.fields)) {
    return { fields: cached.fields, fetchedAt: cached.fetchedAt || 0 };
  }
  return { fields: cached, fetchedAt: 0 };
}

async function getFields({ forceRefresh = false } = {}) {
  if (!forceRefresh) {
    const peeked = await peekCachedFields();
    if (peeked) return peeked.fields;
  }
  return fetchFields();
}

async function getProfile({ forceRefresh = false } = {}) {
  if (!forceRefresh) {
    const stored = await browser.storage.local.get(PROFILE_CACHE_KEY);
    if (stored[PROFILE_CACHE_KEY]) return stored[PROFILE_CACHE_KEY];
  }
  return fetchProfile();
}

async function loadFieldsForAutofill() {
  try {
    const fields = { ...(await getFields({ forceRefresh: true })) };
    const peeked = await peekCachedFields();
    return {
      fields,
      stale: false,
      fetchedAt: (peeked && peeked.fetchedAt) || Date.now(),
    };
  } catch (e) {
    const peeked = await peekCachedFields();
    if (peeked && peeked.fields) {
      return {
        fields: { ...peeked.fields },
        stale: true,
        fetchedAt: peeked.fetchedAt || 0,
      };
    }
    throw e;
  }
}
