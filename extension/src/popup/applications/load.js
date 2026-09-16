function truncateLabel(text) {
  const s = String(text || "").replace(/\s+/g, " ").trim();
  if (s.length <= 80) return s;
  return s.slice(0, 77) + "…";
}

function renderAutofillReport(reply) {
  if (!autofillReport) return;
  autofillReport.innerHTML = "";
  autofillReport.classList.remove("hidden");

  if (reply && reply.needsRefresh) {
    const p = document.createElement("p");
    p.textContent = "Reload the page so InternApplier can attach.";
    autofillReport.appendChild(p);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = "Reload page";
    btn.addEventListener("click", reloadActivePage);
    autofillReport.appendChild(btn);
    return;
  }

  const report = (reply && reply.report) || { filled: [], skipped: [] };
  const filled = Array.isArray(report.filled) ? report.filled : [];
  const skipped = Array.isArray(report.skipped) ? report.skipped : [];
  const already = skipped.filter((s) => s.reason === "already-filled");
  const noValue = skipped.filter((s) => s.reason === "no-value");

  if (!filled.length) {
    const p = document.createElement("p");
    p.textContent = already.length
      ? "No empty fields to fill."
      : "Filled nothing — no recognized fields on this page.";
    autofillReport.appendChild(p);
  } else {
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = `Filled ${filled.length} field${filled.length === 1 ? "" : "s"}`;
    details.appendChild(summary);
    const ul = document.createElement("ul");
    filled.forEach((item) => {
      const li = document.createElement("li");
      li.textContent = truncateLabel(item.label || item.key);
      ul.appendChild(li);
    });
    details.appendChild(ul);
    autofillReport.appendChild(details);
  }

  if (already.length) {
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = `${already.length} field${already.length === 1 ? "" : "s"} already had a value`;
    autofillReport.appendChild(p);
  }
  if (noValue.length) {
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = `${noValue.length} recognized field${noValue.length === 1 ? "" : "s"} had no profile value`;
    autofillReport.appendChild(p);
  }
  if (reply && reply.stale) {
    const p = document.createElement("p");
    p.className = "warn";
    p.textContent = "Used cached profile data — InternApplier may be offline.";
    autofillReport.appendChild(p);
  }
}

loadTarget.addEventListener("change", () => {
  askBtn.disabled = selectedApplicationUuid() == null;
  refreshResumeChip(selectedApplicationUuid());
  patchSession({ selectedUuid: selectedApplicationUuid() }).catch(() => {});
});

loadBtn.addEventListener("click", async () => {
  const uuid = loadTarget.value;
  if (!uuid) {
    showToast("Pick an application.", { kind: "warn" });
    return;
  }
  if (autofillReport) autofillReport.classList.add("hidden");
  showToast("Filling…", { persist: true });
  loadBtn.disabled = true;
  try {
    const reply = await browser.runtime.sendMessage({
      type: "AUTOFILL_WITH_APPLICATION",
      uuid,
    });
    if (reply && reply.needsRefresh) {
      showNeedsRefresh(reply.error || reply.reason);
      renderAutofillReport(reply);
      return;
    }
    if (reply && reply.ok) {
      renderAutofillReport(reply);
      const n = reply.report && Array.isArray(reply.report.filled)
        ? reply.report.filled.length
        : 0;
      let message;
      let kind;
      if (n === 0) {
        message = "Filled nothing — no recognized fields on this page.";
        kind = "warn";
      } else {
        message = `Filled ${n} field${n === 1 ? "" : "s"}.`;
        kind = "ok";
      }
      if (reply.stale) {
        message += " Used cached profile data.";
        kind = "warn";
      }
      showToast(message, { kind });
    } else {
      const detail = reply && (reply.error || reply.reason || `HTTP ${reply.status}`);
      showToast(`Could not autofill: ${detail || "unknown error"}`, { kind: "error" });
    }
  } catch (e) {
    showToast(`Error: ${e.message}`, { kind: "error" });
  } finally {
    loadBtn.disabled = false;
  }
});
