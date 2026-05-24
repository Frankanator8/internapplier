async function refreshResumeChip(uuid) {
  if (!resumeChip || !resumeChipRow) return;
  if (_resumePollUuid && _resumePollUuid !== uuid) stopResumePolling();
  if (!uuid) {
    stopResumePolling();
    hideResumeChip();
    return;
  }
  let reply = null;
  try {
    reply = await browser.runtime.sendMessage({
      type: "FETCH_RESUME",
      uuid,
    });
  } catch (_) {}
  if (loadTarget.value !== uuid) return;
  if (reply && reply.ok && reply.arrayBuffer) {
    if (_resumePollUuid === uuid) stopResumePolling();
    const file = new File([reply.arrayBuffer], reply.filename || "Resume.pdf", {
      type: "application/pdf",
    });
    resumeChip._file = file;
    resumeChip.hidden = false;
    if (resumeChipName) resumeChipName.textContent = file.name;
    if (resumeGenerateBtn) resumeGenerateBtn.hidden = true;
    resumeChipRow.hidden = false;
    return;
  }
  if (reply && reply.status === 404) {
    // No resume yet. If a job is already running for this uuid, keep polling
    // and show the disabled button; otherwise show the actionable button.
    let statusReply = null;
    try {
      statusReply = await browser.runtime.sendMessage({
        type: "GENERATE_RESUME_STATUS",
        uuid,
      });
    } catch (_) {}
    if (loadTarget.value !== uuid) return;
    const running = statusReply && statusReply.ok && statusReply.body
      && statusReply.body.status === "running";
    showResumeGenerateButton(uuid, { generating: !!running });
    if (running) startResumePolling(uuid);
    return;
  }
  hideResumeChip();
}

function startResumePolling(uuid) {
  stopResumePolling();
  _resumePollUuid = uuid;
  const tick = async () => {
    if (_resumePollUuid !== uuid || loadTarget.value !== uuid) {
      stopResumePolling();
      return;
    }
    let reply = null;
    try {
      reply = await browser.runtime.sendMessage({
        type: "GENERATE_RESUME_STATUS",
        uuid,
      });
    } catch (_) {}
    if (_resumePollUuid !== uuid || loadTarget.value !== uuid) return;
    const body = reply && reply.ok ? reply.body : null;
    if (body && body.status === "done") {
      stopResumePolling();
      refreshResumeChip(uuid);
    } else if (body && body.status === "error") {
      stopResumePolling();
      showResumeGenerateButton(uuid, { generating: false });
      if (resultEl) resultEl.textContent = `Resume generation failed: ${body.error || "unknown error"}`;
    } else {
      _resumePollTimer = setTimeout(tick, 3000);
    }
  };
  _resumePollTimer = setTimeout(tick, 3000);
}

if (resumeGenerateBtn) {
  resumeGenerateBtn.addEventListener("click", async () => {
    const uuid = resumeGenerateBtn.dataset.uuid;
    if (!uuid || loadTarget.value !== uuid) return;
    showResumeGenerateButton(uuid, { generating: true });
    if (resultEl) resultEl.textContent = "";
    let reply = null;
    try {
      reply = await browser.runtime.sendMessage({
        type: "GENERATE_RESUME",
        uuid,
      });
    } catch (_) {}
    if (loadTarget.value !== uuid) return;
    if (reply && reply.ok) {
      startResumePolling(uuid);
      return;
    }
    const detail = (reply && reply.body && reply.body.detail)
      || (reply && reply.error)
      || (reply && reply.status ? `HTTP ${reply.status}` : "unknown error");
    showResumeGenerateButton(uuid, { generating: false });
    if (resultEl) resultEl.textContent = `Could not start resume generation: ${detail}`;
  });
}

if (resumeChip) {
  resumeChip.addEventListener("dragstart", (e) => {
    const file = resumeChip._file;
    if (!file) { e.preventDefault(); return; }
    try {
      e.dataTransfer.effectAllowed = "copy";
      e.dataTransfer.items.add(file);
      if (_resumeChipObjectUrl) {
        try { URL.revokeObjectURL(_resumeChipObjectUrl); } catch (_) {}
      }
      _resumeChipObjectUrl = URL.createObjectURL(file);
      e.dataTransfer.setData(
        "DownloadURL",
        `application/pdf:${file.name}:${_resumeChipObjectUrl}`
      );
    } catch (_) {
      // Some browsers throw on items.add for cross-origin; fall through silently.
    }
  });
}
