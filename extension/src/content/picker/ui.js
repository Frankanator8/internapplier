let _pickerState = null;

function stopPicker(result) {
  if (!_pickerState) return;
  const { onMove, onClick, onKey, styleEl, lastEl } = _pickerState;
  document.removeEventListener("mousemove", onMove, true);
  document.removeEventListener("click", onClick, true);
  document.removeEventListener("keydown", onKey, true);
  if (lastEl) lastEl.classList.remove("__ia_picker_hover");
  if (styleEl && styleEl.parentNode) styleEl.parentNode.removeChild(styleEl);
  _pickerState = null;
  try {
    const msgType = result && result.field === "scan_container"
      ? "SCAN_PICKER_RESULT"
      : "PICKER_RESULT";
    browser.runtime.sendMessage({ type: msgType, result });
  } catch (_) { /* popup may be closed */ }
}

function startPicker(field) {
  if (_pickerState) return;
  const styleEl = document.createElement("style");
  styleEl.textContent =
    ".__ia_picker_hover { outline: 2px solid #2563eb !important; " +
    "outline-offset: -2px !important; cursor: crosshair !important; }";
  document.head.appendChild(styleEl);

  const state = { styleEl, lastEl: null, onMove: null, onClick: null, onKey: null, field: field || "description" };
  state.onMove = (e) => {
    if (state.lastEl) state.lastEl.classList.remove("__ia_picker_hover");
    state.lastEl = e.target;
    if (state.lastEl && state.lastEl.classList) {
      state.lastEl.classList.add("__ia_picker_hover");
    }
  };
  state.onClick = (e) => {
    e.preventDefault();
    e.stopPropagation();
    const el = e.target;
    if (state.field === "scan_container") {
      let jobs = [];
      try { jobs = extractJobList(el); } catch (_) {}
      if (jobs.length < 2 && el && el.parentElement) {
        // Single-row sample: treat siblings with matching signature as the list
        try {
          const parent = el.parentElement;
          const sig = signatureFor(el);
          const siblings = Array.from(parent.children).filter((c) => signatureFor(c) === sig);
          if (siblings.length >= 2) {
            const inferred = extractFromRepeatingRows(siblings);
            if (inferred.length > jobs.length) jobs = inferred;
          }
        } catch (_) {}
      }
      if (jobs.length < 1 && el && el.parentElement) {
        try { jobs = extractJobList(el.parentElement); } catch (_) {}
      }
      stopPicker({
        ok: true,
        field: "scan_container",
        jobs,
        selector: bestSelector(el),
      });
      return;
    }
    let value = el ? (el.innerText || el.textContent || "").trim() : "";
    if (state.field === "link") {
      const a = el && (el.closest ? el.closest("a") : null);
      if (a && a.href) value = a.href;
      else value = location.href;
    }
    stopPicker({ ok: true, field: state.field, value });
  };
  state.onKey = (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      stopPicker({ ok: false, field: state.field, cancelled: true });
    }
  };
  _pickerState = state;
  document.addEventListener("mousemove", state.onMove, true);
  document.addEventListener("click", state.onClick, true);
  document.addEventListener("keydown", state.onKey, true);
}
