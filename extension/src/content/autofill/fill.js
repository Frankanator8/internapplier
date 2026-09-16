function setInputValue(el, value) {
  const proto = el instanceof HTMLTextAreaElement
    ? HTMLTextAreaElement.prototype
    : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
  setter.call(el, value);
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
}

function setSelectValue(el, value) {
  const target = normalize(value);
  if (!target) return false;
  let chosen = null;
  for (const opt of el.options) {
    if (normalize(opt.value) === target || normalize(opt.textContent) === target) {
      chosen = opt; break;
    }
  }
  if (!chosen) {
    for (const opt of el.options) {
      const t = normalize(opt.textContent);
      if (t && (t.includes(target) || target.includes(t))) { chosen = opt; break; }
    }
  }
  if (!chosen) return false;
  el.value = chosen.value;
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
  return true;
}

const SKIP_NOISE_TYPES = new Set([
  "hidden", "submit", "button", "reset", "image",
]);
const SKIP_UNSUPPORTED_TYPES = new Set([
  "file", "password", "checkbox", "radio",
]);

const FILL_STYLE_ID = "__ia_fill_style";

function ensureFillStyles() {
  if (document.getElementById(FILL_STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = FILL_STYLE_ID;
  style.textContent =
    ".__ia_filled { outline: 2px solid #0D9488 !important; " +
    "outline-offset: 1px !important; transition: outline-color 0.6s ease; }" +
    ".__ia_filled.__ia_filled_fade { outline-color: transparent !important; }" +
    "#__ia_toast { position: fixed; z-index: 2147483647; right: 16px; bottom: 16px; " +
    "max-width: 280px; padding: 10px 14px; background: #0D9488; color: #fff; " +
    'font: 13px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; ' +
    "border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,.2); pointer-events: none; }";
  (document.head || document.documentElement).appendChild(style);
}

function flashFilled(el) {
  if (!el || !el.classList) return;
  ensureFillStyles();
  el.classList.add("__ia_filled");
  el.classList.remove("__ia_filled_fade");
  setTimeout(() => {
    el.classList.add("__ia_filled_fade");
    setTimeout(() => {
      el.classList.remove("__ia_filled", "__ia_filled_fade");
    }, 700);
  }, 1400);
}

function showPageToast(text) {
  ensureFillStyles();
  let toast = document.getElementById("__ia_toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "__ia_toast";
    (document.body || document.documentElement).appendChild(toast);
  }
  toast.textContent = text;
  clearTimeout(showPageToast._timer);
  showPageToast._timer = setTimeout(() => {
    if (toast && toast.parentNode) toast.parentNode.removeChild(toast);
  }, 4000);
}

function shortLabelFor(el) {
  if (el.labels && el.labels.length) {
    const t = (el.labels[0].textContent || "").replace(/\s+/g, " ").trim();
    if (t) return t;
  }
  if (el.id) {
    try {
      const labeled = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      const t = labeled ? (labeled.textContent || "").replace(/\s+/g, " ").trim() : "";
      if (t) return t;
    } catch (_) {}
  }
  const aria = (el.getAttribute("aria-label") || "").trim();
  if (aria) return aria;
  const ph = (el.getAttribute("placeholder") || "").trim();
  if (ph) return ph;
  const name = (el.getAttribute("name") || el.getAttribute("id") || "")
    .replace(/[_-]+/g, " ").trim();
  return name;
}

function fillField(el, fields) {
  const inputType = el.tagName === "INPUT" ? (el.type || "text").toLowerCase() : "";
  if (el.tagName === "INPUT" && SKIP_NOISE_TYPES.has(inputType)) return null;

  const fullLabel = labelTextFor(el);
  if (!fullLabel) return null;

  const key = matchKey(fullLabel);
  if (!key) return null;
  const label = shortLabelFor(el) || fullLabel;

  if (el.disabled || el.readOnly) {
    return { filled: false, key, label, reason: "unsupported-type" };
  }

  const value = fields[key];
  if (value === undefined || value === null || value === "") {
    return { filled: false, key, label, reason: "no-value" };
  }

  if (el.tagName === "SELECT") {
    if (setSelectValue(el, value)) return { filled: true, key, label };
    return { filled: false, key, label, reason: "no-match" };
  }
  if (el.tagName === "TEXTAREA") {
    if (el.value) return { filled: false, key, label, reason: "already-filled" };
    setInputValue(el, value);
    return { filled: true, key, label };
  }
  if (el.tagName === "INPUT") {
    if (SKIP_UNSUPPORTED_TYPES.has(inputType)) {
      return { filled: false, key, label, reason: "unsupported-type" };
    }
    if (el.value) return { filled: false, key, label, reason: "already-filled" };
    setInputValue(el, value);
    return { filled: true, key, label };
  }
  return { filled: false, key, label, reason: "unsupported-type" };
}

function autofillAll(fields) {
  const report = { filled: [], skipped: [] };
  if (!fields) return report;
  const elements = document.querySelectorAll("input, select, textarea");
  for (const el of elements) {
    try {
      const result = fillField(el, fields);
      if (!result) continue;
      if (result.filled) {
        report.filled.push({ key: result.key, label: result.label });
        flashFilled(el);
      } else {
        report.skipped.push({
          key: result.key,
          label: result.label,
          reason: result.reason,
        });
      }
    } catch (_) { /* keep going */ }
  }
  return report;
}
