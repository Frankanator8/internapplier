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
    ``width_ratio`` is the line's drawn width over the widest body-line
    width observed in the document — a proxy for "how full" the line is.
    """
    from statistics import median

    from pypdf import PdfReader

    reader = PdfReader(str(pdf))
    n_pages = len(reader.pages)
    if n_pages == 0:
        return {"fill": 0.0, "lines": []}

    try:
        # Per page: list of fragments (x, y, text).
        per_page_frags: list[list[tuple[float, float, str]]] = []
        for page in reader.pages:
            frags: list[tuple[float, float, str]] = []

            def visitor(text, cm, tm, font_dict, font_size, _frags=frags):
                if text and text.strip():
                    x = float(tm[4])
                    y = round(float(tm[5]) * 2) / 2
                    _frags.append((x, y, text))

            page.extract_text(visitor_text=visitor)
            per_page_frags.append(frags)

        # Group each page's fragments into lines (by y), then compute
        # x_start/x_end and reconstructed text per line.
        per_page_lines: list[list[dict]] = []
        for frags in per_page_frags:
            by_y: dict[float, list[tuple[float, str]]] = {}
            for x, y, text in frags:
                by_y.setdefault(y, []).append((x, text))
            lines: list[dict] = []
            # Sort y descending so visual top-of-page is first.
            for y in sorted(by_y.keys(), reverse=True):
                parts = sorted(by_y[y], key=lambda p: p[0])
                text = "".join(p[1] for p in parts).strip()
                if not text:
                    continue
                xs = [p[0] for p in parts]
                # Approximate x_end as the x of the last fragment plus a
                # character-width estimate per remaining char. The visitor
                # gives us start-x per fragment but not advance widths;
                # a fixed factor of font_size is unavailable, so use a
                # nominal 5pt-per-char heuristic which is close enough
                # for the short-tail ratio comparison (we only care about
                # relative line widths).
                last_x = xs[-1]
                last_text = parts[-1][1]
                approx_end = last_x + len(last_text) * 5.0
                lines.append({
                    "text": text,
                    "x_start": xs[0],
                    "x_end": approx_end,
                    "y": y,
                })
            per_page_lines.append(lines)

        # Document-wide max line width — proxy for "full line".
        all_widths = [
            ln["x_end"] - ln["x_start"]
            for page in per_page_lines for ln in page
        ]
        max_width = max(all_widths) if all_widths else 1.0
        if max_width <= 0:
            max_width = 1.0

        for page in per_page_lines:
            for idx, ln in enumerate(page):
                width = ln["x_end"] - ln["x_start"]
                ln["width_ratio"] = max(0.0, min(width / max_width, 1.0))
                ln["is_last_on_page"] = idx == len(page) - 1

        # --- fill calculation (same logic as before) ---
        per_page_ys: list[list[float]] = [
            sorted({ln["y"] for ln in page}) for page in per_page_lines
        ]
        line_counts = [len(ys) for ys in per_page_ys]
        if not any(line_counts):
            return {"fill": float(n_pages), "lines": per_page_lines}

        last_lines = line_counts[-1]
        if n_pages >= 2:
            max_lines = max(line_counts[:-1]) or last_lines
        else:
            ys = per_page_ys[0]
            if len(ys) < 2:
                return {"fill": float(n_pages), "lines": per_page_lines}
            diffs = [b - a for a, b in zip(ys, ys[1:]) if b - a > 0.1]
            spacing = median(diffs) if diffs else (ys[-1] - ys[0]) / max(len(ys) - 1, 1)
            page_height = float(reader.pages[0].mediabox.height)
            text_top_margin = page_height - ys[-1]
            text_bottom_margin = ys[0]
            usable = page_height - text_top_margin - text_bottom_margin + spacing
            max_lines = max(int(round(usable / spacing)), last_lines)

        if max_lines <= 0:
            return {"fill": float(n_pages), "lines": per_page_lines}

        fractional = last_lines / max_lines
        fractional = max(0.0, min(fractional, 1.0))
        fill = (n_pages - 1) + fractional
        return {"fill": fill, "lines": per_page_lines}
    except Exception:
        logger.exception("pdf_page_metrics — extraction failed; falling back to raw page count")
        return {"fill": float(n_pages), "lines": []}


def _extract_error_excerpt(log_text: str, max_chars: int = 1500) -> str:
    lines = log_text.splitlines()
    err_idx = next((i for i, ln in enumerate(lines) if ln.startswith("!")), None)
    if err_idx is None:
        return log_text[-max_chars:]
    start = max(0, err_idx - 2)
    end = min(len(lines), err_idx + 15)
    return "\n".join(lines[start:end])[:max_chars]
