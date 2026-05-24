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
