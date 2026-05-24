function stripHtml(html) {
  if (!html) return "";
  const tmp = document.createElement("div");
  tmp.innerHTML = String(html);
  return (tmp.textContent || tmp.innerText || "").replace(/\s+\n/g, "\n").trim();
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

function signatureFor(el) {
  if (!el || el.nodeType !== 1) return "";
  const classes = Array.from(el.classList || []).slice(0, 4).sort().join(".");
  return el.tagName + (classes ? "." + classes : "");
}
