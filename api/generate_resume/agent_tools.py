from __future__ import annotations

import logging
from typing import Any, Callable

from ..ai_provider import load_schema
from ..constants import AGENT_MAX_LOG_EXCERPT
import re

from .compile import (
    LatexCompileError,
    compile_latex,
    pdf_page_metrics,
)
from .render import render_resume, validate_resume_shape

logger = logging.getLogger(__name__)


def _truncate(text: str, limit: int = AGENT_MAX_LOG_EXCERPT) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n…[truncated {len(text) - limit} chars]"


SHORT_TAIL_THRESHOLD = 0.35


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()


def _iter_resume_bullets(resume: dict):
    """Yield every bullet string the renderer will draw, in document order."""
    for section in resume.get("sections") or []:
        kind = section.get("kind")
        if kind in ("experience", "projects"):
            for item in section.get("items") or []:
                for bullet in item.get("bullets") or []:
                    if isinstance(bullet, str) and bullet.strip():
                        yield bullet
        elif kind == "awards":
            for item in section.get("items") or []:
                title = (item.get("title") or "").strip()
                issuer = (item.get("issuer") or "").strip()
                combined = " ".join(p for p in (title, issuer) if p)
                if combined:
                    yield combined


def detect_short_bullets(resume: dict, lines_by_page: list[list[dict]]) -> list[dict]:
    """Identify bullets whose final wrapped line is mostly empty.

    Matches each bullet's normalized text against the concatenation of
    reconstructed PDF lines (also normalized). Records bullets that span
    >=2 lines and whose last line's ``width_ratio`` is below
    :data:`SHORT_TAIL_THRESHOLD`, excluding the last line on each page
    (which is short for an unrelated reason).
    """
    if not lines_by_page:
        return []

    # Flatten lines across pages with metadata; also build a single
    # normalized-text stream with char-offset → line-index mapping.
    flat: list[dict] = []
    for page in lines_by_page:
        for ln in page:
            flat.append(ln)
    if not flat:
        return []

    # Build cumulative normalized text and offset table.
    norm_parts: list[str] = []
    line_offsets: list[tuple[int, int]] = []  # (start, end) per line
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
    for bullet in _iter_resume_bullets(resume):
        needle = _norm_ws(bullet)
        if not needle:
            continue
        idx = haystack.find(needle, search_from)
        if idx < 0:
            # Fall back to global search to tolerate ordering drift.
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


def page_length(resume: Any = None, **_) -> dict[str, Any]:
    """Render `resume` JSON through the configured Jinja template, compile,
    and return its fill, page cap, and any short-tail bullets."""
    # Imported lazily to avoid a circular import (ai_provider <-> agent_tools).
    from api.ai_provider import get_resume_page_cap, get_resume_template

    page_cap = get_resume_page_cap()
    if not isinstance(resume, dict) or not resume:
        return {"ok": False, "page_cap": page_cap, "log_excerpt": "empty or non-object resume argument"}
    try:
        validate_resume_shape(resume)
    except ValueError as e:
        return {"ok": False, "page_cap": page_cap, "log_excerpt": f"schema error: {e}"}
    try:
        latex = render_resume(resume, get_resume_template())
    except Exception as e:
        logger.exception("page_length — render_resume failed")
        return {"ok": False, "page_cap": page_cap, "log_excerpt": f"render error: {e}"}
    try:
        pdf_path = compile_latex(latex)
    except LatexCompileError as e:
        excerpt = getattr(e, "log_excerpt", "") or str(e)
        return {"ok": False, "page_cap": page_cap, "log_excerpt": _truncate(excerpt)}
    try:
        metrics = pdf_page_metrics(pdf_path)
    except Exception as e:
        logger.exception("page_length — pdf_page_metrics failed")
        return {"ok": False, "page_cap": page_cap, "log_excerpt": f"pdf_page_metrics error: {e}"}
    fill = metrics["fill"]
    short_bullets = detect_short_bullets(resume, metrics.get("lines") or [])
    return {
        "ok": True,
        "fill": round(float(fill), 4),
        "page_cap": page_cap,
        "short_bullets": short_bullets,
    }


TOOL_HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {
    "page_length": page_length,
}


OPENAI_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "page_length": load_schema("page_length.tool.json"),
}
