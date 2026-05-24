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
