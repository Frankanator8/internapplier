loadTarget.addEventListener("change", () => {
  askBtn.disabled = selectedApplicationUuid() == null;
  refreshResumeChip(selectedApplicationUuid());
});

loadBtn.addEventListener("click", async () => {
  const uuid = loadTarget.value;
  if (!uuid) {
    resultEl.textContent = "Pick an application.";
    return;
  }
  resultEl.textContent = "Loading…";
  loadBtn.disabled = true;
  try {
    const reply = await browser.runtime.sendMessage({
      type: "AUTOFILL_WITH_APPLICATION",
      uuid,
    });
    if (reply && reply.ok) {
      resultEl.textContent = "Done.";
    } else {
      const detail = reply && (reply.error || reply.reason || `HTTP ${reply.status}`);
      resultEl.textContent = `Could not autofill: ${detail || "unknown error"}`;
    }
  } catch (e) {
    resultEl.textContent = `Error: ${e.message}`;
  } finally {
    loadBtn.disabled = false;
  }
});
