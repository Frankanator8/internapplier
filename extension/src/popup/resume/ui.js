let _resumeChipObjectUrl = null;
let _resumePollTimer = null;
let _resumePollUuid = null;

function hideResumeChip() {
  if (resumeChip) {
    resumeChip._file = null;
    resumeChip.hidden = true;
  }
  if (resumeGenerateBtn) resumeGenerateBtn.hidden = true;
  if (resumeChipRow) resumeChipRow.hidden = true;
  if (_resumeChipObjectUrl) {
    try { URL.revokeObjectURL(_resumeChipObjectUrl); } catch (_) {}
    _resumeChipObjectUrl = null;
  }
}

function stopResumePolling() {
  if (_resumePollTimer) {
    clearTimeout(_resumePollTimer);
    _resumePollTimer = null;
  }
  _resumePollUuid = null;
}

function showResumeGenerateButton(uuid, { generating = false } = {}) {
  if (!resumeGenerateBtn || !resumeChipRow) return;
  if (resumeChip) {
    resumeChip._file = null;
    resumeChip.hidden = true;
  }
  resumeGenerateBtn.hidden = false;
  resumeGenerateBtn.disabled = generating;
  resumeGenerateBtn.textContent = generating ? "Generating…" : "Generate Resume";
  resumeGenerateBtn.dataset.uuid = uuid;
  resumeChipRow.hidden = false;
}
