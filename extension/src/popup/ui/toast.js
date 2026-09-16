function showToast(message, { kind = "info", persist = false } = {}) {
  if (!toastEl) return;
  if (showToast._timer) {
    clearTimeout(showToast._timer);
    showToast._timer = null;
  }
  toastEl.textContent = message || "";
  toastEl.classList.remove("hidden", "error", "ok", "warn");
  if (kind === "error") toastEl.classList.add("error");
  else if (kind === "ok") toastEl.classList.add("ok");
  else if (kind === "warn") toastEl.classList.add("warn");
  if (!persist) {
    showToast._timer = setTimeout(() => {
      toastEl.classList.add("hidden");
    }, 5000);
  }
}

function clearToast() {
  if (showToast._timer) {
    clearTimeout(showToast._timer);
    showToast._timer = null;
  }
  if (!toastEl) return;
  toastEl.classList.add("hidden");
  toastEl.classList.remove("error", "ok", "warn");
  toastEl.textContent = "";
}

function showToastWithAction(message, actionLabel, onClick, { kind = "error" } = {}) {
  if (!toastEl) return;
  if (showToast._timer) {
    clearTimeout(showToast._timer);
    showToast._timer = null;
  }
  toastEl.textContent = "";
  toastEl.classList.remove("hidden", "error", "ok", "warn");
  if (kind === "error") toastEl.classList.add("error");
  else if (kind === "ok") toastEl.classList.add("ok");
  else if (kind === "warn") toastEl.classList.add("warn");
  const text = document.createElement("div");
  text.textContent = message;
  toastEl.appendChild(text);
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "toast-action secondary";
  btn.textContent = actionLabel;
  btn.addEventListener("click", onClick);
  toastEl.appendChild(btn);
}
