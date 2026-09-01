from __future__ import annotations

import logging
import re
from typing import Any, Callable

from ..ai_provider import load_schema
from ..constants import AGENT_MAX_LOG_EXCERPT, RESUME_TARGET_FILL

from .compile import (
    LatexCompileError,
    compile_latex,
    pdf_page_metrics,
)

logger = logging.getLogger(__name__)


_MINIMAL_PREAMBLE = r"""\documentclass[11pt]{article}
\usepackage[margin=0.75in]{geometry}
\usepackage{hyperref}
\usepackage{enumitem}
\usepackage{titlesec}
\begin{document}
"""
_MINIMAL_POSTAMBLE = "\n\\end{document}\n"

_ITEM_RE = re.compile(r"\\item\b\s*(.*?)(?=\\item\b|\\end\{|\Z)", re.DOTALL)
_TEX_WRAP_RE = re.compile(
    r"\\(?:textbf|textit|emph|texttt|underline|textsc)\*?\{([^{}]*)\}"
)
_HREF_RE = re.compile(r"\\href\{[^{}]*\}\{([^{}]*)\}")
_TEX_CMD_RE = re.compile(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?")
_TEX_COMMENT_RE = re.compile(r"(?<!\\)%[^\n]*")


def _wrap_if_snippet(latex: str) -> str:
    if "\\documentclass" in latex:
        return latex
    return _MINIMAL_PREAMBLE + latex + _MINIMAL_POSTAMBLE


def _truncate(text: str, limit: int = AGENT_MAX_LOG_EXCERPT) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n…[truncated {len(text) - limit} chars]"


SHORT_TAIL_THRESHOLD = 0.45


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()


def _strip_tex(s: str) -> str:
    s = _TEX_COMMENT_RE.sub("", s)
    s = _HREF_RE.sub(r"\1", s)
    for _ in range(4):
        nxt = _TEX_WRAP_RE.sub(r"\1", s)
        if nxt == s:
            break
        s = nxt
    s = _TEX_CMD_RE.sub("", s)
    s = s.replace("{", "").replace("}", "")
    return _norm_ws(s)


def _iter_resume_bullets(latex: str):
    """Yield visible bullet text from ``\\item`` lines, in document order."""
    if not latex:
        return
    for match in _ITEM_RE.finditer(latex):
        text = _strip_tex(match.group(1))
        if text:
            yield text


def detect_short_bullets(latex: str, lines_by_page: list[list[dict]]) -> list[dict]:
    """Identify bullets whose final wrapped line is mostly empty.

    Matches each ``\\item``'s normalized text against the concatenation of
    reconstructed PDF lines (also normalized). Records bullets that span
    >=2 lines and whose last line's ``width_ratio`` is below
    :data:`SHORT_TAIL_THRESHOLD`, excluding the last line on each page
    (which is short for an unrelated reason).
    """
    if not latex or not lines_by_page:
        return []

    flat: list[dict] = []
    for page in lines_by_page:
        for ln in page:
            flat.append(ln)
    if not flat:
        return []

    norm_parts: list[str] = []
    line_offsets: list[tuple[int, int]] = []
    cursor = 0
    for ln in flat:
        norm = _norm_ws(ln["text"])
        if cursor > 0:
            norm_parts.append(" ")
            cursor += 1
        start = cursor
        norm_parts.append(norm)
        cursor += len(norm)
        line_offsets.append((start, cursor))
    haystack = "".join(norm_parts)

    def _line_index_at(offset: int) -> int:
        for i, (s, e) in enumerate(line_offsets):
            if s <= offset < e or (i == len(line_offsets) - 1 and offset == e):
                return i
        return len(line_offsets) - 1

    findings: list[dict] = []
    search_from = 0
    for bullet in _iter_resume_bullets(latex):
        needle = _norm_ws(bullet)
        if not needle:
            continue
        idx = haystack.find(needle, search_from)
        if idx < 0:
            idx = haystack.find(needle)
            if idx < 0:
                continue
        end_idx = idx + len(needle) - 1
        first_line = _line_index_at(idx)
        last_line = _line_index_at(end_idx)
        search_from = end_idx + 1

        if last_line <= first_line:
            continue
        last = flat[last_line]
        if last.get("is_last_on_page"):
            continue
        ratio = float(last.get("width_ratio") or 0.0)
        if ratio >= SHORT_TAIL_THRESHOLD:
            continue
        text = bullet if len(bullet) <= 120 else bullet[:117] + "..."
        findings.append({
            "text": text,
            "lines": last_line - first_line + 1,
            "last_line_fill": round(ratio, 2),
        })

    findings.sort(key=lambda f: f["last_line_fill"])
    return findings[:6]


def page_length(latex: Any = None, **_) -> dict[str, Any]:
    """Compile `latex` and return fill, page cap, and any short-tail bullets."""
    from api.ai_provider import get_resume_page_cap

    page_cap = get_resume_page_cap()
    if not isinstance(latex, str) or not latex.strip():
        return {"ok": False, "page_cap": page_cap, "log_excerpt": "empty latex argument"}
    document = _wrap_if_snippet(latex)
    try:
        pdf_path = compile_latex(document)
    except LatexCompileError as e:
        excerpt = getattr(e, "log_excerpt", "") or str(e)
        return {"ok": False, "page_cap": page_cap, "log_excerpt": _truncate(excerpt)}
    try:
        metrics = pdf_page_metrics(pdf_path)
    except Exception as e:
        logger.exception("page_length — pdf_page_metrics failed")
        return {"ok": False, "page_cap": page_cap, "log_excerpt": f"pdf_page_metrics error: {e}"}
    fill = metrics["fill"]
    short_bullets = detect_short_bullets(latex, metrics.get("lines") or [])
    return {
        "ok": True,
        "fill": round(float(fill), 4),
        "page_cap": page_cap,
        "target_fill": RESUME_TARGET_FILL,
        "short_bullets": short_bullets,
    }


TOOL_HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {
    "page_length": page_length,
}


OPENAI_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "page_length": load_schema("page_length.tool.json"),
}
