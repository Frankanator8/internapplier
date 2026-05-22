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
  ["company",             [/company|employer|organization|organisation/]],
  ["role",                [/job\s*title|position|role/]],
  ["description",         [/cover\s*letter|why\s*(do\s*you\s*)?(want|interested)|message|about\s*you/]],
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

function cellText(td) {
  return (td.innerText || td.textContent || "").replace(/\s+/g, " ").trim();
}

function classifyHeader(text) {
  const t = normalize(text);
  if (!t) return null;
  if (/\bcompany|employer|organization\b/.test(t)) return "company";
  if (/\brole|position|job\s*title|title\b/.test(t)) return "role";
  if (/\bapplication|apply|link\b/.test(t)) return "link";
  if (/\blocation|locations?\b/.test(t)) return "location";
  return null;
}

function rowsFromHeaderCells(headerCells, dataRows, getCells) {
  if (!headerCells.length) return [];
  const colMap = {};
  let matched = 0;
  headerCells.forEach((th, i) => {
    const kind = classifyHeader(cellText(th));
    if (kind && colMap[kind] === undefined) {
      colMap[kind] = i;
      matched++;
    }
  });
  if (matched < 2) return [];
  if (colMap.company === undefined && colMap.role === undefined) return [];

  const out = [];
  let lastCompany = "";
  for (const tr of dataRows) {
    const tds = getCells(tr);
    if (!tds || !tds.length) continue;

    const rawCompany = colMap.company !== undefined && tds[colMap.company] ? cellText(tds[colMap.company]) : "";
    const role = colMap.role !== undefined && tds[colMap.role] ? cellText(tds[colMap.role]) : "";
    const location = colMap.location !== undefined && tds[colMap.location] ? cellText(tds[colMap.location]) : "";
    const linkCell = colMap.link !== undefined ? tds[colMap.link] : null;

    let company = rawCompany;
    const stripped = company.replace(/^[\s↳⮑→\-•*]+/, "").trim();
    if (!stripped || /^(↳|⮑|→)/.test(rawCompany)) {
      company = lastCompany;
    } else {
      company = stripped;
      lastCompany = company;
    }

    if (linkCell) {
      const cellHtml = linkCell.innerHTML || "";
      if (/🔒|closed/i.test(cellHtml) && !linkCell.querySelector("a[href]")) continue;
    }

    let link = "";
    if (linkCell) {
      const a = linkCell.querySelector("a[href]");
      if (a) link = a.href;
    }
    if (!link) {
      // Fallback: any <a href> in the row
      for (const td of tds) {
        if (!td) continue;
        const a = td.querySelector ? td.querySelector("a[href]") : null;
        if (a && a.href && !/^(mailto:|javascript:|#)/i.test(a.getAttribute("href") || "")) {
          link = a.href;
          break;
        }
      }
    }
    if (!link) continue;
    if (!company && !role) continue;

    out.push({ company, role, link, location });
  }
  return out;
}

function extractJobsFromTable(table) {
  let headerCells = table.querySelectorAll("thead th, thead td");
  let dataRows = Array.from(table.querySelectorAll("tbody tr"));
  if (!headerCells.length) {
    // Fallback: first <tr> is header, rest are data
    const allRows = Array.from(table.querySelectorAll("tr"));
    if (allRows.length < 2) return [];
    headerCells = allRows[0].querySelectorAll("th, td");
    dataRows = allRows.slice(1);
  }
  return rowsFromHeaderCells(headerCells, dataRows, (tr) => Array.from(tr.children));
}

function extractJobsFromAriaGrid(root) {
  const results = [];
  const grids = root.querySelectorAll('[role="table"], [role="grid"], [role="list"]');
  for (const grid of grids) {
    let headerCells = Array.from(grid.querySelectorAll('[role="columnheader"]'));
    let rows = Array.from(grid.querySelectorAll('[role="row"], [role="listitem"]'));
    // If a header row exists among rows, peel it off
    if (!headerCells.length && rows.length) {
      const firstRowHeaders = rows[0].querySelectorAll('[role="columnheader"]');
      if (firstRowHeaders.length) {
        headerCells = Array.from(firstRowHeaders);
        rows = rows.slice(1);
      }
    }
    if (headerCells.length && rows.length) {
      try {
        const got = rowsFromHeaderCells(
          headerCells,
          rows,
          (r) => {
            const cells = r.querySelectorAll('[role="cell"], [role="gridcell"]');
            return cells.length ? Array.from(cells) : Array.from(r.children);
          }
        );
        for (const g of got) results.push(g);
      } catch (_) { /* ignore */ }
    }
    // Heuristic fallback inside an aria grid/list: use repeating-row inference
    if (!results.length) {
      try {
        const inferred = extractFromRepeatingRows(rows.length ? rows : Array.from(grid.children));
        for (const g of inferred) results.push(g);
      } catch (_) {}
    }
  }
  return results;
}

function pickLocation(text) {
  if (!text) return "";
  const m = text.match(/\b[A-Z][a-zA-Z .'-]+,\s*[A-Z]{2,}(?:,\s*[A-Za-z]+)?/);
  if (m) return m[0].trim();
  if (/\bremote\b/i.test(text)) {
    const m2 = text.match(/[^\n,]*\bremote\b[^\n,]*/i);
    return (m2 ? m2[0] : "Remote").trim();
  }
  return "";
}

function deepText(el, max) {
  if (!el) return "";
  const t = (el.innerText || el.textContent || "").replace(/\s+/g, " ").trim();
  return max ? t.slice(0, max) : t;
}

function extractFromRepeatingRows(rows) {
  const out = [];
  for (const row of rows) {
    if (!row || row.nodeType !== 1) continue;
    const text = deepText(row);
    if (!text) continue;
    const anchors = Array.from(row.querySelectorAll("a[href]")).filter((a) => {
      const href = a.getAttribute("href") || "";
      return href && !/^(mailto:|javascript:|#)/i.test(href);
    });
    if (!anchors.length) continue;

    // Role: longest anchor text, or first heading
    let role = "";
    const heading = row.querySelector("h1, h2, h3, h4, h5, [role='heading']");
    if (heading) role = deepText(heading, 200);
    if (!role) {
      let best = "";
      for (const a of anchors) {
        const t = deepText(a, 200);
        if (t.length > best.length) best = t;
      }
      role = best;
    }

    // Company: try data attrs / aria-labels, else fall back to other anchor text
    let company = "";
    const compEl = row.querySelector(
      '[data-company], [data-company-name], [class*="company" i], [aria-label*="company" i]'
    );
    if (compEl) company = deepText(compEl, 120);
    if (!company) {
      for (const a of anchors) {
        const t = deepText(a, 120);
        if (t && t !== role) { company = t; break; }
      }
    }

    // Location
    const location = pickLocation(text);

    // Link: first non-trivial anchor
    const link = anchors[0].href;

    if (!role && !company) continue;
    out.push({ company, role, link, location });
  }
  return out;
}

function signatureFor(el) {
  if (!el || el.nodeType !== 1) return "";
  const classes = Array.from(el.classList || []).slice(0, 4).sort().join(".");
  return el.tagName + (classes ? "." + classes : "");
}

function extractJobsFromRepeatingList(root) {
  const results = [];
  // Candidate containers: root + descendants with ≥ 4 element children
  const candidates = [root];
  const all = root.querySelectorAll ? root.querySelectorAll("*") : [];
  for (const el of all) {
    if (el.children && el.children.length >= 4) candidates.push(el);
  }
  for (const container of candidates) {
    const kids = Array.from(container.children || []);
    if (kids.length < 4) continue;
    // Group by signature
    const groups = new Map();
    for (const k of kids) {
      const sig = signatureFor(k);
      if (!sig) continue;
      if (!groups.has(sig)) groups.set(sig, []);
      groups.get(sig).push(k);
    }
    for (const [, group] of groups) {
      if (group.length < 4) continue;
      // Must contain at least one anchor in most rows
      const withLinks = group.filter((r) => r.querySelector && r.querySelector("a[href]"));
      if (withLinks.length < Math.max(2, Math.floor(group.length * 0.5))) continue;
      const rows = extractFromRepeatingRows(group);
      for (const r of rows) results.push(r);
    }
  }
  return results;
}

function extractJobList(rootEl) {
  const root = rootEl || document;
  const seen = new Set();
  const results = [];
  const push = (r) => {
    const key = (r.link || "") + "|" + normalize(r.company) + "|" + normalize(r.role);
    if (seen.has(key)) return;
    seen.add(key);
    results.push(r);
  };

  // Strategy A: real <table>
  const tables = root.querySelectorAll ? root.querySelectorAll("table") : [];
  for (const table of tables) {
    try {
      const rows = extractJobsFromTable(table);
      for (const r of rows) push(r);
    } catch (_) {}
  }
  if (root !== document && root.tagName === "TABLE") {
    try {
      const rows = extractJobsFromTable(root);
      for (const r of rows) push(r);
    } catch (_) {}
  }

  // Strategy B: ARIA grid
  try {
    const rows = extractJobsFromAriaGrid(root);
    for (const r of rows) push(r);
  } catch (_) {}

  // Strategy C: repeating-sibling lists
  try {
    const rows = extractJobsFromRepeatingList(root);
    for (const r of rows) push(r);
  } catch (_) {}

  return results;
}

function extractJobListWithRetry(rootEl, timeoutMs) {
  const initial = extractJobList(rootEl);
  if (initial.length > 0 || rootEl) {
    return Promise.resolve(initial);
  }
  // No results and scanning the whole document — wait briefly for SPA content
  return new Promise((resolve) => {
    let done = false;
    const finish = (jobs) => {
      if (done) return;
      done = true;
      try { observer.disconnect(); } catch (_) {}
      clearTimeout(timer);
      resolve(jobs);
    };
    const observer = new MutationObserver(() => {
      try {
        const got = extractJobList();
        if (got.length > 0) finish(got);
      } catch (_) {}
    });
    try {
      observer.observe(document.body, { childList: true, subtree: true });
    } catch (_) {
      finish(initial);
      return;
    }
    const timer = setTimeout(() => finish(extractJobList()), timeoutMs || 1500);
  });
}

function bestSelector(el) {
  if (!el || el.nodeType !== 1) return "";
  if (el.id) return `#${CSS.escape(el.id)}`;
  const parts = [];
  let cur = el;
  for (let i = 0; i < 4 && cur && cur.nodeType === 1 && cur !== document.body; i++) {
    let part = cur.tagName.toLowerCase();
    if (cur.id) { parts.unshift(`#${CSS.escape(cur.id)}`); break; }
    if (cur.parentElement) {
      const same = Array.from(cur.parentElement.children).filter(
        (c) => c.tagName === cur.tagName
      );
      if (same.length > 1) {
        const idx = same.indexOf(cur) + 1;
        part += `:nth-of-type(${idx})`;
      }
    }
    parts.unshift(part);
    cur = cur.parentElement;
  }
  return parts.join(" > ");
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
  if (msg && msg.type === "EXTRACT_JOB_LIST") {
    let root = null;
    if (msg.selector) {
      try { root = document.querySelector(msg.selector); } catch (_) {}
    }
    return extractJobListWithRetry(root, 1500).then(
      (jobs) => ({ ok: true, jobs }),
      (e) => ({ ok: false, error: String(e && e.message || e), jobs: [] })
    );
  }
});

(async function autoRunOnLoad() {
  try {
    const fields = await browser.runtime.sendMessage({ type: "GET_FIELDS" });
    if (fields) autofillAll(fields);
  } catch (_) { /* server not running — silent */ }
})();
