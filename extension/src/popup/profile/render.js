function makeChip(value, label) {
  const text = String(value == null ? "" : value);
  if (!text.trim()) return null;
  const chip = document.createElement("span");
  chip.className = "chip";
  chip.setAttribute("draggable", "true");
  const preview = text.length > 60 ? text.slice(0, 57) + "…" : text;
  if (label) {
    const lbl = document.createElement("span");
    lbl.className = "chip-label";
    lbl.textContent = label + ":";
    chip.appendChild(lbl);
  }
  chip.appendChild(document.createTextNode(preview));
  chip.title = text;
  chip.addEventListener("dragstart", (e) => {
    e.dataTransfer.setData("text/plain", text);
    e.dataTransfer.effectAllowed = "copy";
  });
  return chip;
}

function appendChipRow(container, fieldName, value) {
  if (value == null || String(value).trim() === "") return;
  const chip = makeChip(value);
  if (!chip) return;
  const row = document.createElement("div");
  row.className = "chip-row";
  const name = document.createElement("span");
  name.className = "field-name";
  name.textContent = fieldName;
  row.appendChild(name);
  row.appendChild(chip);
  container.appendChild(row);
}

function makeTreeNode(title, openByDefault) {
  const d = document.createElement("details");
  d.className = "tree";
  if (openByDefault) d.open = true;
  d.dataset.defaultOpen = openByDefault ? "1" : "0";
  const s = document.createElement("summary");
  s.textContent = title;
  d.appendChild(s);
  const body = document.createElement("div");
  body.className = "tree-body";
  d.appendChild(body);
  return { details: d, body };
}

function renderDict(container, obj) {
  if (!obj || typeof obj !== "object") return;
  for (const [k, v] of Object.entries(obj)) {
    if (v == null) continue;
    if (typeof v === "object") {
      if (Array.isArray(v)) {
        if (!v.length) continue;
        const node = makeTreeNode(k, false);
        for (let i = 0; i < v.length; i++) {
          const item = v[i];
          if (item && typeof item === "object" && !Array.isArray(item)) {
            const inner = makeTreeNode(`#${i + 1}`, false);
            renderDict(inner.body, item);
            node.body.appendChild(inner.details);
          } else if (Array.isArray(item)) {
            const inner = makeTreeNode(`#${i + 1}`, false);
            for (let j = 0; j < item.length; j++) appendChipRow(inner.body, String(j + 1), item[j]);
            node.body.appendChild(inner.details);
          } else {
            appendChipRow(node.body, String(i + 1), item);
          }
        }
        container.appendChild(node.details);
      } else {
        const node = makeTreeNode(k, false);
        renderDict(node.body, v);
        container.appendChild(node.details);
      }
    } else {
      appendChipRow(container, k, v);
    }
  }
}

async function renderProfilePanel() {
  profileTree.innerHTML = "";
  let profile = null;
  try {
    profile = await browser.runtime.sendMessage({ type: "GET_PROFILE" });
  } catch (_) {}
  if (!profile || typeof profile !== "object") {
    profileSection.classList.add("hidden");
    return;
  }
  const order = [
    "general_info",
    "experience",
    "projects",
    "education",
    "awards",
    "skills",
    "hobbies",
    "applications",
  ];
  for (const key of order) {
    if (!(key in profile)) continue;
    const v = profile[key];
    if (v == null) continue;
    if (typeof v === "object") {
      const node = makeTreeNode(key, key === "general_info");
      if (Array.isArray(v)) {
        if (!v.length) continue;
        for (let i = 0; i < v.length; i++) {
          const item = v[i];
          const title = (item && (item.company || item.role || item.name || item.title)) || `#${i + 1}`;
          if (item && typeof item === "object" && !Array.isArray(item)) {
            const inner = makeTreeNode(String(title), false);
            renderDict(inner.body, item);
            node.body.appendChild(inner.details);
          } else {
            appendChipRow(node.body, String(i + 1), item);
          }
        }
      } else {
        renderDict(node.body, v);
      }
      profileTree.appendChild(node.details);
    } else {
      appendChipRow(profileTree, key, v);
    }
  }
  profileSection.classList.remove("hidden");
  applyProfileFilter();
}
