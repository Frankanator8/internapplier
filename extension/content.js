// Field-matching aliases. Each key matches a profile field returned by
// /autofill/fields. Patterns are tested against a normalized label string
// (lowercased, whitespace-collapsed) built from <label>, name, id,
// placeholder, and aria-label.
const ALIASES = [
  ["first_name",          [/first\s*name/, /given\s*name/, /\bfname\b/]],
  ["last_name",           [/last\s*name/, /family\s*name/, /surname/, /\blname\b/]],
  ["preferred_name",      [/preferred\s*name/, /nickname/]],
  ["pronouns",            [/pronouns?/]],
  ["email",               [/e[-\s]?mail/]],
  ["phone",               [/phone/, /mobile/, /telephone/, /\btel\b/]],
  ["address1",            [/address\s*(line)?\s*1/, /street\s*address/, /\baddress\b(?!.*2)/]],
  ["address2",            [/address\s*(line)?\s*2/, /apt|apartment|suite|unit/]],
  ["city",                [/city|town|locality/]],
  ["state",               [/state|province|region/]],
  ["postal_code",         [/postal|zip/]],
  ["country",             [/country/]],
  ["linkedin",            [/linked\s*in/]],
  ["website",             [/website|portfolio|personal\s*site|homepage/]],
  ["github",              [/github/]],
  ["earliest_start_date", [/start\s*date|availability|available|earliest/]],
  ["desired_salary",      [/salary|compensation|expected\s*pay|desired\s*pay/]],
  ["date_of_birth",       [/date\s*of\s*birth|birth\s*date|\bdob\b/]],
  ["employment_status",   [/employment\s*status|current\s*employment/]],
  ["work_authorization",  [/work\s*authorization|authorized\s*to\s*work|us\s*work\s*auth/]],
  ["require_sponsorship", [/sponsorship|visa\s*sponsor|require.*visa/]],
  ["willing_to_relocate", [/relocat/]],
  ["gender",              [/\bgender\b/]],
  ["ethnicity",           [/ethnic|race/]],
  ["veteran_status",      [/veteran/]],
  ["disability_status",   [/disab/]],
];

function normalize(s) {
  return (s || "").toString().toLowerCase().replace(/\s+/g, " ").trim();
}

function labelTextFor(el) {
  const parts = [];
  if (el.labels && el.labels.length) {
    for (const l of el.labels) parts.push(l.textContent || "");
  } else if (el.id) {
    const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
    if (l) parts.push(l.textContent || "");
  }
  let p = el.parentElement;
  for (let i = 0; i < 3 && p; i++, p = p.parentElement) {
    if (p.tagName === "LABEL") { parts.push(p.textContent || ""); break; }
  }
  parts.push(el.getAttribute("aria-label") || "");
  parts.push(el.getAttribute("placeholder") || "");
  parts.push(el.getAttribute("name") || "");
  parts.push(el.getAttribute("id") || "");
  return normalize(parts.join(" "));
}

function matchKey(label) {
  for (const [key, patterns] of ALIASES) {
    for (const pat of patterns) {
      if (pat.test(label)) return key;
    }
  }
  return null;
}

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

function stripHtml(html) {
  if (!html) return "";
  const tmp = document.createElement("div");
  tmp.innerHTML = String(html);
  return (tmp.textContent || tmp.innerText || "").replace(/\s+\n/g, "\n").trim();
}

function extractJobPosting() {
  const scripts = document.querySelectorAll('script[type="application/ld+json"]');
  for (const s of scripts) {
    let parsed;
    try { parsed = JSON.parse(s.textContent || ""); } catch (_) { continue; }
    const items = Array.isArray(parsed) ? parsed : [parsed];
    for (const item of items) {
      if (!item || typeof item !== "object") continue;
      const type = item["@type"];
      const isPosting = type === "JobPosting"
        || (Array.isArray(type) && type.includes("JobPosting"));
      if (!isPosting) continue;
      const org = item.hiringOrganization;
      const company = (org && typeof org === "object" ? org.name : org) || "";
      return {
        role: String(item.title || "").trim(),
        company: String(company || "").trim(),
        description: stripHtml(item.description || ""),
      };
    }
  }
  return null;
}

function metaContent(selector) {
  const el = document.querySelector(selector);
  return el ? (el.getAttribute("content") || "").trim() : "";
}

function splitTitle(title) {
  if (!title) return { role: "", company: "" };
  const seps = [" - ", " – ", " — ", " | ", " at ", " @ "];
  for (const sep of seps) {
    const idx = title.indexOf(sep);
    if (idx > 0) {
      return {
        role: title.slice(0, idx).trim(),
        company: title.slice(idx + sep.length).trim(),
      };
    }
  }
  return { role: title.trim(), company: "" };
}

function extractPageMeta() {
  const jp = extractJobPosting();
  if (jp && (jp.role || jp.company || jp.description)) {
    return {
      url: location.href,
      title: document.title,
      role: jp.role,
      company: jp.company,
      description: jp.description,
    };
  }
  const ogSite = metaContent('meta[property="og:site_name"]');
  const ogTitle = metaContent('meta[property="og:title"]');
  const split = splitTitle(ogTitle || document.title || "");
  return {
    url: location.href,
    title: document.title,
    role: split.role,
    company: ogSite || split.company,
    description: "",
  };
}

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
    browser.runtime.sendMessage({ type: "PICKER_RESULT", result });
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

browser.runtime.onMessage.addListener((msg) => {
  if (msg && msg.type === "AUTOFILL") {
    const filled = autofillAll(msg.fields);
    return Promise.resolve({ filled });
  }
  if (msg && msg.type === "EXTRACT_PAGE_META") {
    try {
      return Promise.resolve(extractPageMeta());
    } catch (e) {
      return Promise.resolve({
        url: location.href, title: document.title,
        role: "", company: "", description: "",
        error: String(e && e.message || e),
      });
    }
  }
  if (msg && msg.type === "START_PICKER") {
    startPicker(msg.field);
    return Promise.resolve({ ok: true });
  }
});

(async function autoRunOnLoad() {
  try {
    const fields = await browser.runtime.sendMessage({ type: "GET_FIELDS" });
    if (fields) autofillAll(fields);
  } catch (_) { /* server not running — silent */ }
})();
