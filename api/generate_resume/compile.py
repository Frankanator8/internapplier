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

    Returns ``full_pages + (lines_on_last_page / max_lines_per_page)``.
    A single-page resume that's three-quarters full returns ``0.75``;
    one filling 1 page + 75% of a second returns ``1.75``.
    """
    from statistics import median

    from pypdf import PdfReader

    reader = PdfReader(str(pdf))
    n_pages = len(reader.pages)
    if n_pages == 0:
        return 0.0

    try:
        per_page_ys: list[list[float]] = []
        for page in reader.pages:
            ys: list[float] = []

            def visitor(text, cm, tm, font_dict, font_size, _ys=ys):
                if text and text.strip():
                    _ys.append(round(float(tm[5]) * 2) / 2)

            page.extract_text(visitor_text=visitor)
            per_page_ys.append(sorted(set(ys)))

        line_counts = [len(ys) for ys in per_page_ys]
        if not any(line_counts):
            return float(n_pages)

        last_lines = line_counts[-1]
        if n_pages >= 2:
            max_lines = max(line_counts[:-1]) or last_lines
        else:
            ys = per_page_ys[0]
            if len(ys) < 2:
                return float(n_pages)
            diffs = [b - a for a, b in zip(ys, ys[1:]) if b - a > 0.1]
            spacing = median(diffs) if diffs else (ys[-1] - ys[0]) / max(len(ys) - 1, 1)
            page_height = float(reader.pages[0].mediabox.height)
            text_top_margin = page_height - ys[-1]
            text_bottom_margin = ys[0]
            usable = page_height - text_top_margin - text_bottom_margin + spacing
            max_lines = max(int(round(usable / spacing)), last_lines)

        if max_lines <= 0:
            return float(n_pages)

        fractional = last_lines / max_lines
        fractional = max(0.0, min(fractional, 1.0))
        return (n_pages - 1) + fractional
    except Exception:
        logger.exception("pdf_page_fill — extraction failed; falling back to raw page count")
        return float(n_pages)


def _extract_error_excerpt(log_text: str, max_chars: int = 1500) -> str:
    lines = log_text.splitlines()
    err_idx = next((i for i, ln in enumerate(lines) if ln.startswith("!")), None)
    if err_idx is None:
        return log_text[-max_chars:]
    start = max(0, err_idx - 2)
    end = min(len(lines), err_idx + 15)
    return "\n".join(lines[start:end])[:max_chars]
