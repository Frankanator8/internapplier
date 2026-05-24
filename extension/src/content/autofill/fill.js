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

const SKIP_INPUT_TYPES = new Set([
  "hidden", "submit", "button", "reset", "file", "image", "password",
  "checkbox", "radio",
]);

function fillField(el, fields) {
  if (el.disabled || el.readOnly) return false;
  const label = labelTextFor(el);
  if (!label) return false;
  const key = matchKey(label);
  if (!key) return false;
  const value = fields[key];
  if (value === undefined || value === null || value === "") return false;

  if (el.tagName === "SELECT") {
    return setSelectValue(el, value);
  }
  if (el.tagName === "TEXTAREA") {
    if (el.value) return false;
    setInputValue(el, value);
    return true;
  }
  if (el.tagName === "INPUT") {
    const t = (el.type || "text").toLowerCase();
    if (SKIP_INPUT_TYPES.has(t)) return false;
    if (el.value) return false;
    setInputValue(el, value);
    return true;
  }
  return false;
}

function autofillAll(fields) {
  if (!fields) return 0;
  const elements = document.querySelectorAll("input, select, textarea");
  let filled = 0;
  for (const el of elements) {
    try {
      if (fillField(el, fields)) filled++;
    } catch (_) { /* keep going */ }
  }
  return filled;
}
