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
