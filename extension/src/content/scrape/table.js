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
