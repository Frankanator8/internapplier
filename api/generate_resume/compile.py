from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

_DOCUMENTCLASS_RE = re.compile(r"\\documentclass\s*(?:\[[^\]]*\])?\s*\{")
_END_DOCUMENT_RE = re.compile(r"\\end\s*\{document\}")


def extract_document(text: str) -> str | None:
    """Return the substring from a real ``\\documentclass{...}`` through
    ``\\end{document}``. Returns None if no real ``\\documentclass{...}``
    declaration is present — bare mentions of ``\\documentclass`` inside
    prose (e.g. backtick-quoted commentary) are ignored because they lack
    the following ``{`` argument."""
    start = _DOCUMENTCLASS_RE.search(text)
    if not start:
        return None
    end = _END_DOCUMENT_RE.search(text, start.end())
    if not end:
        return text[start.start():]
    return text[start.start():end.end()]

logger = logging.getLogger(__name__)


class LatexCompileError(RuntimeError):
    def __init__(self, message: str, log_excerpt: str = ""):
        super().__init__(message)
        self.log_excerpt = log_excerpt


_SMART_CHAR_MAP = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": "``", "”": "''", "„": ",,",
    "–": "--", "—": "---",
    "…": "...",
    " ": " ",
}


def _scrub_smart_chars(latex: str) -> str:
    """Replace Unicode quotes/dashes pdflatex (default fontenc) chokes on."""
    out = latex
    replaced = 0
    for src, dst in _SMART_CHAR_MAP.items():
        if src in out:
            replaced += out.count(src)
            out = out.replace(src, dst)
    if replaced:
        logger.info("compile_latex — scrubbed %d smart char(s) before compile", replaced)
    return out


def _preflight_latex(latex: str) -> None:
    """Cheap sanity checks before invoking pdflatex.

    Raises LatexCompileError with a precise message when a problem is
    structurally obvious, so feedback to the next attempt is short and
    targeted instead of a 1500-char compiler log.
    """
    if "\\begin{document}" not in latex:
        raise LatexCompileError(
            "Missing \\begin{document} — generated source is incomplete."
        )
    if "\\end{document}" not in latex:
        raise LatexCompileError(
            "Missing \\end{document} — generated source was truncated."
        )
    depth = 0
    i = 0
    n = len(latex)
    while i < n:
        ch = latex[i]
        if ch == "%":
            nl = latex.find("\n", i)
            i = n if nl < 0 else nl + 1
            continue
        if ch == "\\" and i + 1 < n and latex[i + 1] in "{}%&_#$":
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                raise LatexCompileError(
                    f"Unbalanced braces in LaTeX (extra '}}' near char {i})."
                )
        i += 1
    if depth != 0:
        raise LatexCompileError(
            f"Unbalanced braces in LaTeX ({depth} '{{' left unclosed)."
        )


def compile_latex(latex: str, workdir: Path | None = None) -> Path:
    if shutil.which("pdflatex") is None:
        raise LatexCompileError(
            "pdflatex not found on PATH; install a TeX distribution (e.g. MacTeX, TeX Live)."
        )

    latex = _scrub_smart_chars(latex)
    _preflight_latex(latex)

    if workdir is None:
        workdir = Path(tempfile.mkdtemp(prefix="resume_"))
    workdir.mkdir(parents=True, exist_ok=True)

    tex_path = workdir / "resume.tex"
    tex_path.write_text(latex, encoding="utf-8")

    last_stdout = ""
    for pass_idx in (1, 2):
        try:
            proc = subprocess.run(
                [
                    "pdflatex",
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    "-output-directory",
                    str(workdir),
                    str(tex_path),
                ],
                cwd=str(workdir),
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            raise LatexCompileError("pdflatex timed out after 60s.")

        last_stdout = proc.stdout or ""
        if proc.returncode != 0:
            log_path = workdir / "resume.log"
            log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else last_stdout
            excerpt = _extract_error_excerpt(log_text)
            logger.error("compile_latex — pass %d failed rc=%d", pass_idx, proc.returncode)
            raise LatexCompileError(
                f"pdflatex failed (pass {pass_idx}, rc={proc.returncode}).",
                log_excerpt=excerpt,
            )

    pdf_path = workdir / "resume.pdf"
    if not pdf_path.exists():
        raise LatexCompileError("pdflatex returned 0 but resume.pdf was not produced.")

    logger.info("compile_latex — success: %s", pdf_path)
    return pdf_path


def pdf_page_fill(pdf: Path) -> float:
    """Measure how many pages of content the PDF holds, line-wise.

    Backward-compatible wrapper around :func:`pdf_page_metrics`.
    """
    return pdf_page_metrics(pdf)["fill"]


def pdf_page_metrics(pdf: Path) -> dict:
    """Measure page fill and reconstruct per-line geometry.

    Returns ``{"fill": float, "lines": list[list[dict]]}`` where ``lines``
    is one list per page; each entry is
    ``{"text": str, "x_start": float, "x_end": float, "y": float,
       "width_ratio": float, "is_last_on_page": bool}``.
    ``width_ratio`` is the line's drawn width over the document's text
    column width (right edge minus left edge) — a proxy for "how full"
    the line is, independent of any left indent.

    ``fill`` is measured geometrically against the page's real text area
    (inferred margins), not against line density within the content span
    — a page with generous section spacing but few lines should not read
    as "full", and a page with tight single-spaced content should not
    read as "empty" just because the block of text is short.
    """
    from statistics import median

    from pypdf import PdfReader

    reader = PdfReader(str(pdf))
    n_pages = len(reader.pages)
    if n_pages == 0:
        return {"fill": 0.0, "lines": []}

    try:
        # Per page: list of fragments (x, y, text, font_size).
        per_page_frags: list[list[tuple[float, float, str, float]]] = []
        for page in reader.pages:
            frags: list[tuple[float, float, str, float]] = []

            def visitor(text, cm, tm, font_dict, font_size, _frags=frags):
                if text and text.strip():
                    x = float(tm[4])
                    y = round(float(tm[5]) * 2) / 2
                    fs = float(font_size) if font_size else 0.0
                    _frags.append((x, y, text, fs))

            page.extract_text(visitor_text=visitor)
            per_page_frags.append(frags)

        # Group each page's fragments into lines (by y).
        per_page_by_y: list[dict[float, list[tuple[float, str, float]]]] = []
        for frags in per_page_frags:
            by_y: dict[float, list[tuple[float, str, float]]] = {}
            for x, y, text, fs in frags:
                by_y.setdefault(y, []).append((x, text, fs))
            per_page_by_y.append(by_y)

        # Calibrate a per-character advance ratio (advance / font_size) from
        # consecutive same-line fragments, pooled across the whole document.
        # The visitor gives per-fragment start-x but not glyph advance
        # widths, so this recovers an empirical estimate instead of a
        # hardcoded points-per-char constant that ignores font size.
        ratio_samples: list[float] = []
        for by_y in per_page_by_y:
            for parts in by_y.values():
                ordered = sorted(parts, key=lambda p: p[0])
                for (cur_x, cur_text, cur_fs), (next_x, _next_text, _next_fs) in zip(ordered, ordered[1:]):
                    advance = next_x - cur_x
                    if advance <= 0 or not cur_text or cur_fs <= 0:
                        continue
                    per_char = advance / len(cur_text)
                    ratio = per_char / cur_fs
                    if 0 < ratio < 2.0:
                        ratio_samples.append(ratio)
        char_advance_ratio = median(ratio_samples) if ratio_samples else 0.5

        # Detect page furniture — e.g. the page number LaTeX's default
        # `\pagestyle{plain}` draws in the footer of every page unless the
        # document explicitly disables it. It is always the page's
        # bottom-most text fragment, isolated from the real content block
        # by a gap far larger than the body's own line spacing. Left in,
        # it drags the inferred "bottom of content" down to the page edge
        # on nearly every document, making `fill` read as ~full (a whole
        # number) almost universally regardless of actual content.
        #
        # The robust body-gap reference is computed only from pages with
        # >=3 distinct lines, so a single footer gap on a sparse page
        # can't skew the median it's later compared against.
        raw_per_page_ys = [sorted(by_y.keys()) for by_y in per_page_by_y]
        robust_gaps = [
            b - a
            for ys in raw_per_page_ys if len(ys) >= 3
            for a, b in zip(ys, ys[1:])
            if b - a > 1.0
        ]
        robust_line_gap = median(robust_gaps) if robust_gaps else 12.0

        furniture_y_by_page: list[float | None] = []
        for ys in raw_per_page_ys:
            candidate = None
            if len(ys) >= 2 and (ys[1] - ys[0]) > max(3.0 * robust_line_gap, 20.0):
                candidate = ys[0]
            furniture_y_by_page.append(candidate)

        # Build reconstructed lines with a calibrated x_end estimate.
        per_page_lines: list[list[dict]] = []
        for page_idx, by_y in enumerate(per_page_by_y):
            lines: list[dict] = []
            furniture_y = furniture_y_by_page[page_idx]
            # Sort y descending so visual top-of-page is first.
            for y in sorted(by_y.keys(), reverse=True):
                if furniture_y is not None and y == furniture_y:
                    continue
                parts = sorted(by_y[y], key=lambda p: p[0])
                text = "".join(p[1] for p in parts).strip()
                if not text:
                    continue
                xs = [p[0] for p in parts]
                last_x, last_text, last_fs = parts[-1]
                fs_for_estimate = last_fs if last_fs > 0 else 10.0
                approx_end = last_x + len(last_text) * char_advance_ratio * fs_for_estimate
                lines.append({
                    "text": text,
                    "x_start": xs[0],
                    "x_end": approx_end,
                    "y": y,
                })
            per_page_lines.append(lines)

        # Document-wide text column — proxy for "full line" independent of
        # any left indent (e.g. wrapped bullet continuation lines).
        all_lines = [ln for page in per_page_lines for ln in page]
        left_edge = min((ln["x_start"] for ln in all_lines), default=0.0)
        right_edge = max((ln["x_end"] for ln in all_lines), default=1.0)
        column_width = right_edge - left_edge
        if column_width <= 0:
            column_width = 1.0

        for page in per_page_lines:
            for idx, ln in enumerate(page):
                width = ln["x_end"] - left_edge
                ln["width_ratio"] = max(0.0, min(width / column_width, 1.0))
                ln["is_last_on_page"] = idx == len(page) - 1

        # --- geometric fill calculation ---
        per_page_ys: list[list[float]] = [
            sorted({ln["y"] for ln in page}) for page in per_page_lines
        ]
        line_counts = [len(ys) for ys in per_page_ys]
        if not any(line_counts):
            return {"fill": float(n_pages), "lines": per_page_lines}

        # Median baseline-to-baseline gap, pooled across all pages, ignoring
        # sub-point diffs from float rounding. Used only as a floor below.
        all_diffs: list[float] = []
        for ys in per_page_ys:
            all_diffs.extend(b - a for a, b in zip(ys, ys[1:]) if b - a > 1.0)
        line_gap = median(all_diffs) if all_diffs else 12.0

        page_heights = [float(page.mediabox.height) for page in reader.pages]

        pages_with_lines = [i for i, ys in enumerate(per_page_ys) if ys]
        # Top margin: min over pages of (page_height - max_y). Taking the
        # min avoids page 1's large name/header line (whose baseline sits
        # well below the glyph top) inflating the inferred margin.
        top_margin = min(
            page_heights[i] - per_page_ys[i][-1] for i in pages_with_lines
        )
        top_margin = max(0.0, top_margin)

        # Bottom margin: a filled (non-final) page reveals the true bottom
        # of the text area. With a single page there's nothing to infer
        # it from, so mirror the top margin — true for `geometry` with a
        # symmetric `margin=` and for article's defaults.
        non_final_with_lines = [i for i in pages_with_lines if i < n_pages - 1]
        if non_final_with_lines:
            bottom_margin = min(per_page_ys[i][0] for i in non_final_with_lines)
            bottom_margin = max(0.0, bottom_margin)
        else:
            bottom_margin = top_margin

        last_height = page_heights[-1]
        usable = last_height - top_margin - bottom_margin
        if usable <= 0:
            return {"fill": float(n_pages), "lines": per_page_lines}

        last_ys = per_page_ys[-1]
        if not last_ys:
            fractional = 0.0
        else:
            min_y_last = last_ys[0]
            used = (last_height - top_margin) - min_y_last
            fractional = used / usable
            # A trailing page holding even one line near its top should
            # not read as "empty" (used ~= 0 there) — floor it to one
            # line's worth. The floor itself is capped at 1.0 so a
            # degenerate `line_gap` (e.g. a near-empty document with too
            # few lines to estimate real spacing) can never push a
            # genuinely short page's fill above "one full page".
            floor = min(line_gap / usable, 1.0)
            fractional = max(floor, min(fractional, 1.0))

        fill = (n_pages - 1) + fractional
        return {"fill": fill, "lines": per_page_lines}
    except Exception:
        logger.exception("pdf_page_metrics — extraction failed; falling back to raw page count")
        return {"fill": float(n_pages), "lines": []}


_BLANK_RUN_RE = re.compile(r"\n{3,}")


def pdf_plain_text(pdf: Path) -> str:
    """Extract the PDF's selectable text — the same content an ATS parser
    or a copy-paste out of the PDF would see. Returns ``""`` on any
    extraction failure rather than raising, since this feeds a grading
    step that can simply skip when there's nothing to grade."""
    from pypdf import PdfReader

    try:
        reader = PdfReader(str(pdf))
    except Exception:
        logger.exception("pdf_plain_text — could not open %s", pdf)
        return ""

    pages: list[str] = []
    for page in reader.pages:
        try:
            text = page.extract_text(extraction_mode="layout")
        except TypeError:
            text = page.extract_text()
        except Exception:
            logger.warning("pdf_plain_text — page extraction failed, skipping page")
            continue
        pages.append("\n".join(line.rstrip() for line in (text or "").splitlines()))

    return _BLANK_RUN_RE.sub("\n\n", "\n\n".join(pages)).strip()


def _extract_error_excerpt(log_text: str, max_chars: int = 1500) -> str:
    lines = log_text.splitlines()
    err_idx = next((i for i, ln in enumerate(lines) if ln.startswith("!")), None)
    if err_idx is None:
        return log_text[-max_chars:]
    start = max(0, err_idx - 2)
    end = min(len(lines), err_idx + 15)
    return "\n".join(lines[start:end])[:max_chars]
