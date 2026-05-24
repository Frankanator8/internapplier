async function getStatuses({ forceRefresh = false } = {}) {
  if (!forceRefresh) {
    const stored = await browser.storage.local.get(STATUSES_CACHE_KEY);
    if (stored[STATUSES_CACHE_KEY]) return stored[STATUSES_CACHE_KEY];
  }
  return fetchStatuses();
}

async function getFields({ forceRefresh = false } = {}) {
  if (!forceRefresh) {
    const stored = await browser.storage.local.get(CACHE_KEY);
    if (stored[CACHE_KEY]) return stored[CACHE_KEY];
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
