function focusHeading(el) {
  if (!el) return;
  if (!el.hasAttribute("tabindex")) el.setAttribute("tabindex", "-1");
  try { el.focus(); } catch (_) {}
}

function showForm() {
  mainView.classList.add("hidden");
  scanView.classList.add("hidden");
  formView.classList.remove("hidden");
  patchSession({ view: "form" }).catch(() => {});
  focusHeading(document.getElementById("form-title"));
}

function showMain() {
  formView.classList.add("hidden");
  scanView.classList.add("hidden");
  mainView.classList.remove("hidden");
  patchSession({ view: "main" }).catch(() => {});
  focusHeading(appTitle);
}

function showScan() {
  formView.classList.add("hidden");
  mainView.classList.add("hidden");
  scanView.classList.remove("hidden");
  patchSession({ view: "scan" }).catch(() => {});
  focusHeading(document.getElementById("scan-title"));
}
