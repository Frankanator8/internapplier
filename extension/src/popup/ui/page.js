async function reloadActivePage() {
  try {
    const reply = await browser.runtime.sendMessage({ type: "RELOAD_ACTIVE_TAB" });
    if (reply && reply.ok) {
      showToast("Page reloading…", { kind: "ok" });
      return;
    }
  } catch (_) {}
  showToast("Reload the tab in Firefox, then try again.", { kind: "error", persist: true });
}

function showNeedsRefresh(detail) {
  showToastWithAction(
    detail || "Reload the page so InternApplier can attach.",
    "Reload page",
    reloadActivePage,
    { kind: "error" }
  );
}

async function startPagePicker(field, prompt) {
  try {
    const reply = await browser.runtime.sendMessage({ type: "START_PICKER", field });
    if (reply && reply.ok) {
      showToast(prompt, { persist: true });
      return true;
    }
    if (reply && reply.needsRefresh) {
      showNeedsRefresh(reply.reason);
      return false;
    }
    showToast((reply && reply.reason) || "Could not start picker.", { kind: "error" });
    return false;
  } catch (e) {
    showToast(`Error: ${e.message}`, { kind: "error" });
    return false;
  }
}
